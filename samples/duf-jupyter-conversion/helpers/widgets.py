import asyncio
import os
import ssl
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import aiohttp
import ipywidgets as widgets
from pyproj import CRS

from .conversion import convert_duf_to_evo
from .portal import build_portal_url


async def create_duf_widget(manager, cache_location: str = "notebook-data"):
    # Capture the current event loop for use in button callbacks
    event_loop = asyncio.get_running_loop()

    # Preload and helpers
    selected_file_path = None
    epsg_valid = False

    def read_env_vars(env_path: Path):
        env = {}
        if env_path.exists():
            try:
                with open(env_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        env[k] = v.strip().strip('"')
            except Exception:
                pass
        return env

    def update_env_var(env_path: Path, key: str, value: str):
        lines = []
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if not line.startswith(f"{key}="):
                        lines.append(line)
        lines.append(f"{key}={value}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)

    env_file_path = Path(cache_location) / ".env"
    os.makedirs(cache_location, exist_ok=True)
    env_vars = read_env_vars(env_file_path)

    # Widgets
    select_button = widgets.Button(
        description="Select DUF File",
        tooltip="Click to select a .duf file",
        style={"button_color": "#265C7F", "text_color": "white"},
    )
    output_label = widgets.Label(value="No file selected")
    status_label = widgets.Label(value="")

    # EPSG code input widget
    epsg_input = widgets.Text(
        description="EPSG code:",
        placeholder="(required), eg. 4326",
        style={"description_width": "initial"},
    )
    epsg_info = widgets.Label(value="Enter EPSG code and press Enter to validate")
    epsg_link = widgets.HTML(
        value='<a href="https://epsg.io" target="_blank" style="font-size: 12px;">Visit epsg.io to find an EPSG code</a>'
    )

    # Object path input widget
    object_path_input = widgets.Text(
        description="Object path:",
        placeholder="(optional), eg. /duf/converted ",
        style={"description_width": "initial"},
    )

    # Conversion section: only show Convert button + timer
    convert_button = widgets.Button(
        description="Convert",
        tooltip="Start the DUF conversion process",
        style={"button_color": "#265C7F", "text_color": "white"},
    )
    timer_label = widgets.HTML(value="", layout=widgets.Layout(margin="4px 0 0 0"))
    status_message = widgets.HTML(value="", layout=widgets.Layout(margin="4px 0 0 0"))
    workspace_link = widgets.HTML(value="", layout=widgets.Layout(margin="4px 0 0 0"))

    convert_section = widgets.VBox(
        [convert_button, timer_label, status_message, workspace_link],
        layout=widgets.Layout(border="1px solid #ccc", padding="10px", margin="5px 0px", display="none"),
    )

    # EPSG box with border
    epsg_box = widgets.VBox(
        [epsg_input, epsg_info, epsg_link],
        layout=widgets.Layout(border="1px solid #ccc", padding="10px", margin="5px 0px"),
    )

    # Object path box with border
    object_path_box = widgets.VBox(
        [object_path_input], layout=widgets.Layout(border="1px solid #ccc", padding="10px", margin="5px 0px")
    )

    advanced_box = widgets.VBox([epsg_box, object_path_box])
    advanced_box.layout.display = "none"

    def update_summary():
        """Show/hide the convert section based on validation state"""
        nonlocal selected_file_path, epsg_valid
        if selected_file_path and epsg_valid:
            convert_section.layout.display = ""
        else:
            convert_section.layout.display = "none"

    def validate_epsg(change):
        """Validate EPSG code using pyproj"""
        nonlocal epsg_valid
        code = change["new"].strip() if isinstance(change, dict) else change.value.strip()
        if not code:
            epsg_info.value = "Enter EPSG code"
            epsg_info.style = {}
            epsg_valid = False
            update_summary()
            return
        epsg_info.value = "Validating..."
        try:
            crs = CRS.from_epsg(int(code))
            epsg_info.value = f"Valid: {crs.name}"
            epsg_info.style = {"text_color": "green"}
            epsg_valid = True
            update_env_var(env_file_path, "EPSG_CODE", code)
            update_summary()
        except ValueError:
            epsg_info.value = "Invalid: EPSG code must be a number"
            epsg_info.style = {"text_color": "red"}
            epsg_valid = False
            update_summary()
        except Exception:
            epsg_info.value = f"Invalid: EPSG:{code} not found"
            epsg_info.style = {"text_color": "red"}
            epsg_valid = False
            update_summary()

    def on_button_click(b):
        """Handle button click to open file dialog"""
        nonlocal selected_file_path
        status_label.value = ""
        output_label.value = "Opening file dialog..."
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        file_path = filedialog.askopenfilename(
            title="Select DUF File", filetypes=[("DUF Files", "*.duf"), ("All Files", "*.*")]
        )
        root.destroy()
        if not file_path:
            output_label.value = "No file selected"
            status_label.value = ""
            advanced_box.layout.display = "none"
            update_summary()
            return
        file_path = Path(file_path)
        if file_path.suffix.lower() != ".duf":
            status_label.value = "ERROR: Invalid file type. Only .duf files are allowed."
            status_label.style = {"text_color": "red"}
            output_label.value = "No file selected"
            advanced_box.layout.display = "none"
            update_summary()
            return
        selected_file_path = str(file_path)
        update_env_var(env_file_path, "SELECTED_DUF_FILE", selected_file_path)
        output_label.value = f"Selected: {file_path.name}"
        status_label.value = "Valid DUF file"
        status_label.style = {"text_color": "green"}
        advanced_box.layout.display = ""
        update_summary()
        print(f"Full path: {selected_file_path}")
        print(f"Updated {env_file_path} with unique SELECTED_DUF_FILE entry")

    def on_object_path_change(change):
        update_env_var(env_file_path, "OBJECT_PATH", change["new"] or "")
        update_summary()

    epsg_input.observe(validate_epsg, names="value")
    select_button.on_click(on_button_click)
    object_path_input.observe(on_object_path_change, names="value")

    # Apply preload state
    saved_path = env_vars.get("SELECTED_DUF_FILE")
    if saved_path:
        p = Path(saved_path)
        if p.suffix.lower() != ".duf":
            status_label.value = "ERROR: Saved file is not a .duf file"
            status_label.style = {"text_color": "red"}
        elif p.exists():
            selected_file_path = str(p)
            output_label.value = f"Selected: {p.name}"
            status_label.value = "Valid DUF file"
            status_label.style = {"text_color": "green"}
            advanced_box.layout.display = ""  # show inputs
            saved_epsg = env_vars.get("EPSG_CODE", "")
            if saved_epsg:
                epsg_input.value = saved_epsg
                try:
                    crs = CRS.from_epsg(int(saved_epsg))
                    epsg_info.value = f"Valid: {crs.name}"
                    epsg_info.style = {"text_color": "green"}
                    epsg_valid = True
                except Exception:
                    epsg_info.value = f"Invalid: EPSG:{saved_epsg} not found"
                    epsg_info.style = {"text_color": "red"}
                    epsg_valid = False
            object_path_input.value = env_vars.get("OBJECT_PATH", "")
            update_summary()
        else:
            status_label.value = "ERROR: Saved file not found on disk"
            status_label.style = {"text_color": "red"}

    # Conversion handler
    def format_hms(seconds: float) -> str:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def on_convert_click(b):
        convert_button.disabled = True
        select_button.disabled = True
        epsg_input.disabled = True
        object_path_input.disabled = True

        start_time = time.time()
        stop_event = threading.Event()
        timer_label.value = "<span style='color:#0b74de;font-weight:600'>Converting... 00:00:00</span>"

        def tick():
            while not stop_event.is_set():
                elapsed = time.time() - start_time
                timer_label.value = (
                    f"<span style='color:#0b74de;font-weight:600'>Converting... {format_hms(elapsed)}</span>"
                )
                time.sleep(0.25)

        # Clear previous status and link
        status_message.value = ""
        workspace_link.value = ""

        t = threading.Thread(target=tick, daemon=True)
        t.start()

        async def do_convert():
            """Async conversion function with retry logic for SSL errors"""
            max_retries = 3
            retry_count = 0

            while retry_count < max_retries:
                try:
                    epsg_code = int(epsg_input.value.strip())
                    upload_path = object_path_input.value.strip() or ""
                    object_metadata = await convert_duf_to_evo(selected_file_path, epsg_code, upload_path, manager)

                    # Display link to open workspace
                    if object_metadata:
                        num_objects = len(object_metadata) if isinstance(object_metadata, list) else 1
                        status_message.value = f"<div style='color:green;font-weight:600'>✓ Published {num_objects} object(s) successfully</div>"
                        # Handle both single object and list of objects
                        obj = object_metadata[0] if isinstance(object_metadata, list) else object_metadata
                        workspace_url = build_portal_url(obj)
                        workspace_link.value = f'<a href="{workspace_url}" target="_blank">Open Evo workspace</a>'
                    else:
                        status_message.value = (
                            "<div style='color:orange;font-weight:600'>⚠ Something went wrong...</div>"
                        )
                    break  # Success, exit retry loop

                except (aiohttp.ClientOSError, ssl.SSLError):
                    retry_count += 1
                    if retry_count < max_retries:
                        status_message.value = f"<div style='color:orange;font-weight:600'>Connection issue, retrying... (attempt {retry_count + 1}/{max_retries})</div>"
                        await asyncio.sleep(1)  # Wait before retry
                    else:
                        status_message.value = (
                            f"<div style='color:red;font-weight:600'>SSL connection failed after {max_retries} attempts.<br>"
                            f"Please restart the kernel and try again.</div>"
                        )
                except ValueError as e:
                    status_message.value = f"<div style='color:red;font-weight:600'>ERROR: {str(e)}</div>"
                    break
                except ConnectionError as e:
                    status_message.value = f"<div style='color:red;font-weight:600'>ERROR: {str(e)}</div>"
                    break
                except Exception as e:
                    status_message.value = (
                        f"<div style='color:red;font-weight:600'>ERROR: {type(e).__name__} - {str(e)}</div>"
                    )
                    break

            # Cleanup (always runs regardless of success/failure)
            stop_event.set()
            t.join(timeout=1.0)
            convert_button.disabled = False
            select_button.disabled = False
            epsg_input.disabled = False
            object_path_input.disabled = False

        # Schedule the async conversion on the captured event loop
        asyncio.run_coroutine_threadsafe(do_convert(), event_loop)

    convert_button.on_click(on_convert_click, remove=True)
    convert_button.on_click(on_convert_click)

    # File selection box with border
    file_selection_box = widgets.VBox(
        [select_button, output_label, status_label],
        layout=widgets.Layout(border="1px solid #ccc", padding="10px", margin="0px"),
    )

    # Display the widget
    ui = widgets.VBox([file_selection_box, advanced_box, convert_section], layout=widgets.Layout(margin="0px"))
    return ui
