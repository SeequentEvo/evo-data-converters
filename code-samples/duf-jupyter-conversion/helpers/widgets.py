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

from .conversion import convert_duf_to_evo, read_duf_layers
from .portal import build_portal_url


def bordered_box_layout():
    return widgets.Layout(border="1px solid #ccc", padding="10px", margin="5px 0px")


def hidden_bordered_box_layout():
    return widgets.Layout(border="1px solid #ccc", padding="10px", margin="5px 0px", display="none")


def status_layout():
    return widgets.Layout(margin="4px 0 0 0")


def read_env_vars(env_path: Path) -> dict:
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


def format_hms(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def validate_epsg_code(code: str):
    """Validate an EPSG code string. Returns (is_valid, message)."""
    if not code:
        return False, "Enter EPSG code"
    try:
        from pyproj import CRS

        crs = CRS.from_epsg(int(code))
        return True, f"Valid: {crs.name}"
    except ValueError:
        return False, "Invalid: EPSG code must be a number"
    except Exception:
        return False, f"Invalid: EPSG:{code} not found"


def open_duf_file_dialog() -> str | None:
    """Open a file dialog to select a .duf file. Returns the path or None."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.askopenfilename(
        title="Select DUF File", filetypes=[("DUF Files", "*.duf"), ("All Files", "*.*")]
    )
    root.destroy()
    return file_path or None


def create_file_selection_widgets():
    """Create the file selection button, output label, and status label."""
    select_button = widgets.Button(
        description="Select DUF File",
        tooltip="Click to select a .duf file",
        style={"button_color": "#265C7F", "text_color": "white"},
    )
    output_label = widgets.Label(value="No file selected")
    status_label = widgets.Label(value="")
    box = widgets.VBox(
        [select_button, output_label, status_label],
        layout=widgets.Layout(border="1px solid #ccc", padding="10px", margin="0px"),
    )
    return select_button, output_label, status_label, box


def create_epsg_widgets():
    """Create EPSG input, info label, link, and containing box."""
    epsg_input = widgets.Text(
        description="EPSG code:", placeholder="(required), eg. 4326", style={"description_width": "initial"}
    )
    epsg_info = widgets.Label(value="Enter EPSG code and press Enter to validate")
    epsg_link = widgets.HTML(
        value='<a href="https://epsg.io" target="_blank" style="font-size: 12px;">Visit epsg.io to find an EPSG code</a>'
    )
    box = widgets.VBox([epsg_input, epsg_info, epsg_link], layout=bordered_box_layout())
    return epsg_input, epsg_info, epsg_link, box


def create_object_path_widgets():
    """Create object path input and containing box."""
    object_path_input = widgets.Text(
        description="Object path:",
        placeholder="(optional), eg. /duf/converted ",
        style={"description_width": "initial"},
    )
    box = widgets.VBox([object_path_input], layout=bordered_box_layout())
    return object_path_input, box


def create_convert_section(button_description="Convert", button_tooltip="Start the DUF conversion process"):
    """Create convert button, timer, status, workspace link, and containing box."""
    convert_button = widgets.Button(
        description=button_description, tooltip=button_tooltip, style={"button_color": "#265C7F", "text_color": "white"}
    )
    timer_label = widgets.HTML(value="", layout=status_layout())
    status_message = widgets.HTML(value="", layout=status_layout())
    workspace_link = widgets.HTML(value="", layout=status_layout())
    box = widgets.VBox(
        [convert_button, timer_label, status_message, workspace_link], layout=hidden_bordered_box_layout()
    )
    return convert_button, timer_label, status_message, workspace_link, box


def run_timed_conversion(event_loop, timer_label, status_message, workspace_link, disable_widgets: list, async_task):
    """Run an async conversion task with a timer and disable/enable widgets around it.

    Args:
        event_loop: The asyncio event loop to schedule on.
        timer_label: HTML widget for the timer display.
        status_message: HTML widget for status messages.
        workspace_link: HTML widget for the workspace link.
        disable_widgets: List of widgets to disable during conversion.
        async_task: An async callable(stop_event) that performs the actual work.
    """
    for w in disable_widgets:
        w.disabled = True

    start_time = time.time()
    stop_event = threading.Event()
    timer_label.value = "<span style='color:#0b74de;font-weight:600'>Converting... 00:00:00</span>"
    status_message.value = ""
    workspace_link.value = ""

    def tick():
        while not stop_event.is_set():
            elapsed = time.time() - start_time
            timer_label.value = (
                f"<span style='color:#0b74de;font-weight:600'>Converting... {format_hms(elapsed)}</span>"
            )
            time.sleep(0.25)

    t = threading.Thread(target=tick, daemon=True)
    t.start()

    async def wrapper():
        try:
            await async_task()
        finally:
            stop_event.set()
            t.join(timeout=1.0)
            for w in disable_widgets:
                w.disabled = False

    asyncio.run_coroutine_threadsafe(wrapper(), event_loop)


async def run_with_retry(coroutine_fn, status_message, max_retries=3):
    """Run a coroutine with retry logic for SSL errors.

    Args:
        coroutine_fn: An async callable that performs the work. Should return on success.
        status_message: HTML widget for status messages.
        max_retries: Number of retries for SSL errors.

    Returns:
        The return value of coroutine_fn on success, or None on failure.
    """
    retry_count = 0
    while retry_count < max_retries:
        try:
            return await coroutine_fn()
        except (aiohttp.ClientOSError, ssl.SSLError):
            retry_count += 1
            if retry_count < max_retries:
                status_message.value = f"<div style='color:orange;font-weight:600'>Connection issue, retrying... (attempt {retry_count + 1}/{max_retries})</div>"
                await asyncio.sleep(1)
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
            status_message.value = f"<div style='color:red;font-weight:600'>ERROR: {type(e).__name__} - {str(e)}</div>"
            break
    return None


def apply_preload_state(env_vars, env_file_path, output_label, status_label, epsg_input, epsg_info, object_path_input):
    """Apply saved environment state to widgets. Returns (selected_file_path, epsg_valid, show_advanced)."""
    selected_file_path = None
    epsg_valid = False
    show_advanced = False

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
            show_advanced = True
            saved_epsg = env_vars.get("EPSG_CODE", "")
            if saved_epsg:
                epsg_input.value = saved_epsg
                valid, msg = validate_epsg_code(saved_epsg)
                epsg_info.value = msg
                epsg_info.style = {"text_color": "green" if valid else "red"}
                epsg_valid = valid
            object_path_input.value = env_vars.get("OBJECT_PATH", "")
        else:
            status_label.value = "ERROR: Saved file not found on disk"
            status_label.style = {"text_color": "red"}

    return selected_file_path, epsg_valid, show_advanced


async def create_duf_widget(manager, cache_location: str = "notebook-data"):
    event_loop = asyncio.get_running_loop()

    env_file_path = Path(cache_location) / ".env"
    os.makedirs(cache_location, exist_ok=True)
    env_vars = read_env_vars(env_file_path)

    select_button, output_label, status_label, file_selection_box = create_file_selection_widgets()
    epsg_input, epsg_info, _, epsg_box = create_epsg_widgets()
    object_path_input, object_path_box = create_object_path_widgets()
    convert_button, timer_label, status_message, workspace_link, convert_section = create_convert_section()

    advanced_box = widgets.VBox([epsg_box, object_path_box])
    advanced_box.layout.display = "none"

    state = {"selected_file_path": None, "epsg_valid": False}

    def update_summary():
        if state["selected_file_path"] and state["epsg_valid"]:
            convert_section.layout.display = ""
        else:
            convert_section.layout.display = "none"

    def on_epsg_change(change):
        code = change["new"].strip()
        if not code:
            epsg_info.value = "Enter EPSG code"
            epsg_info.style = {}
            state["epsg_valid"] = False
            update_summary()
            return
        epsg_info.value = "Validating..."
        valid, msg = validate_epsg_code(code)
        epsg_info.value = msg
        epsg_info.style = {"text_color": "green" if valid else "red"}
        state["epsg_valid"] = valid
        if valid:
            update_env_var(env_file_path, "EPSG_CODE", code)
        update_summary()

    def on_button_click(b):
        status_label.value = ""
        output_label.value = "Opening file dialog..."
        file_path = open_duf_file_dialog()
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
        state["selected_file_path"] = str(file_path)
        update_env_var(env_file_path, "SELECTED_DUF_FILE", state["selected_file_path"])
        output_label.value = f"Selected: {file_path.name}"
        status_label.value = "Valid DUF file"
        status_label.style = {"text_color": "green"}
        advanced_box.layout.display = ""
        update_summary()

    def on_object_path_change(change):
        update_env_var(env_file_path, "OBJECT_PATH", change["new"] or "")
        update_summary()

    epsg_input.observe(on_epsg_change, names="value")
    select_button.on_click(on_button_click)
    object_path_input.observe(on_object_path_change, names="value")

    selected, epsg_valid, show_advanced = apply_preload_state(
        env_vars, env_file_path, output_label, status_label, epsg_input, epsg_info, object_path_input
    )
    state["selected_file_path"] = selected
    state["epsg_valid"] = epsg_valid
    if show_advanced:
        advanced_box.layout.display = ""
    update_summary()

    def on_convert_click(b):
        async def do_convert():
            async def task():
                epsg_code = int(epsg_input.value.strip())
                upload_path = object_path_input.value.strip() or ""
                object_metadata = await convert_duf_to_evo(state["selected_file_path"], epsg_code, upload_path, manager)
                if object_metadata:
                    num_objects = len(object_metadata) if isinstance(object_metadata, list) else 1
                    status_message.value = f"<div style='color:green;font-weight:600'>✓ Published {num_objects} object(s) successfully</div>"
                    obj = object_metadata[0] if isinstance(object_metadata, list) else object_metadata
                    workspace_url = build_portal_url(obj)
                    workspace_link.value = f'<a href="{workspace_url}" target="_blank">Open Evo workspace</a>'
                else:
                    status_message.value = "<div style='color:orange;font-weight:600'>⚠ Something went wrong...</div>"
                return object_metadata

            await run_with_retry(task, status_message)

        run_timed_conversion(
            event_loop,
            timer_label,
            status_message,
            workspace_link,
            [convert_button, select_button, epsg_input, object_path_input],
            do_convert,
        )

    convert_button.on_click(on_convert_click)

    ui = widgets.VBox([file_selection_box, advanced_box, convert_section], layout=widgets.Layout(margin="0px"))
    return ui


async def create_duf_widget_advanced(manager, cache_location: str = "notebook-data"):
    event_loop = asyncio.get_running_loop()

    env_file_path = Path(cache_location) / ".env"
    os.makedirs(cache_location, exist_ok=True)
    env_vars = read_env_vars(env_file_path)

    select_button, output_label, status_label, file_selection_box = create_file_selection_widgets()
    epsg_input, epsg_info, _, epsg_box = create_epsg_widgets()
    object_path_input, object_path_box = create_object_path_widgets()
    convert_button, timer_label, status_message, workspace_link, convert_section = create_convert_section(
        button_description="Convert & Publish", button_tooltip="Convert selected layers and publish to Evo"
    )

    read_layers_button = widgets.Button(
        description="Read Layers",
        tooltip="Read the DUF file and list available layers",
        style={"button_color": "#265C7F", "text_color": "white"},
    )
    read_layers_status = widgets.HTML(value="", layout=status_layout())
    read_layers_section = widgets.VBox([read_layers_button, read_layers_status], layout=hidden_bordered_box_layout())

    select_all_layers_cb = widgets.Checkbox(value=False, description="Select All Layers", indent=False)
    layer_checkboxes_container = widgets.VBox()
    layer_selection_section = widgets.VBox(
        [select_all_layers_cb, layer_checkboxes_container], layout=hidden_bordered_box_layout()
    )

    advanced_box = widgets.VBox([epsg_box, object_path_box])
    advanced_box.layout.display = "none"

    state = {"selected_file_path": None, "epsg_valid": False, "layer_checkboxes": []}

    def update_summary():
        layers_selected = any(cb.value for cb in state["layer_checkboxes"])
        if state["selected_file_path"] and state["epsg_valid"] and layers_selected:
            convert_section.layout.display = ""
        else:
            convert_section.layout.display = "none"

    def on_epsg_change(change):
        code = change["new"].strip()
        if not code:
            epsg_info.value = "Enter EPSG code"
            epsg_info.style = {}
            state["epsg_valid"] = False
            update_summary()
            return
        epsg_info.value = "Validating..."
        valid, msg = validate_epsg_code(code)
        epsg_info.value = msg
        epsg_info.style = {"text_color": "green" if valid else "red"}
        state["epsg_valid"] = valid
        if valid:
            update_env_var(env_file_path, "EPSG_CODE", code)
        update_summary()

    def on_button_click(b):
        status_label.value = ""
        output_label.value = "Opening file dialog..."
        file_path = open_duf_file_dialog()
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
        state["selected_file_path"] = str(file_path)
        update_env_var(env_file_path, "SELECTED_DUF_FILE", state["selected_file_path"])
        output_label.value = f"Selected: {file_path.name}"
        status_label.value = "Valid DUF file"
        status_label.style = {"text_color": "green"}
        read_layers_section.layout.display = ""
        layer_selection_section.layout.display = "none"
        advanced_box.layout.display = "none"
        update_summary()

    def on_object_path_change(change):
        update_env_var(env_file_path, "OBJECT_PATH", change["new"] or "")
        update_summary()

    epsg_input.observe(on_epsg_change, names="value")
    select_button.on_click(on_button_click)
    object_path_input.observe(on_object_path_change, names="value")

    def on_read_layers_click(b):
        read_layers_button.disabled = True
        select_button.disabled = True
        read_layers_status.value = "<span style='color:#0b74de;font-weight:600'>Reading DUF file...</span>"

        layer_selection_section.layout.display = "none"
        advanced_box.layout.display = "none"
        convert_section.layout.display = "none"

        async def do_read():
            try:
                loop = asyncio.get_running_loop()
                layer_info = await loop.run_in_executor(None, read_duf_layers, state["selected_file_path"])

                layer_cbs = []

                def on_layer_change(_change):
                    update_summary()

                for info in layer_info:
                    cb = widgets.Checkbox(
                        value=False, description=f"{info['name']}", indent=False, layout=widgets.Layout(width="auto")
                    )
                    cb.observe(on_layer_change, names="value")
                    layer_cbs.append(cb)

                state["layer_checkboxes"] = layer_cbs

                def on_select_all_layers(change):
                    for cb in state["layer_checkboxes"]:
                        cb.value = change["new"]

                select_all_layers_cb.value = False
                select_all_layers_cb.unobserve_all()
                select_all_layers_cb.observe(on_select_all_layers, names="value")

                layer_checkboxes_container.children = layer_cbs

                read_layers_status.value = f"<div style='color:green;font-weight:600'>✓ Found {len(layer_info)} layer(s). Select layers to convert:</div>"
                layer_selection_section.layout.display = ""
                advanced_box.layout.display = ""
                update_summary()

            except Exception as e:
                read_layers_status.value = (
                    f"<div style='color:red;font-weight:600'>ERROR: {type(e).__name__} - {str(e)}</div>"
                )
            finally:
                read_layers_button.disabled = False
                select_button.disabled = False

        asyncio.run_coroutine_threadsafe(do_read(), event_loop)

    read_layers_button.on_click(on_read_layers_click)

    selected, epsg_valid, show_advanced = apply_preload_state(
        env_vars, env_file_path, output_label, status_label, epsg_input, epsg_info, object_path_input
    )
    state["selected_file_path"] = selected
    state["epsg_valid"] = epsg_valid
    if show_advanced:
        read_layers_section.layout.display = ""
    update_summary()

    def on_convert_click(b):
        async def do_convert():
            async def task():
                epsg_code = int(epsg_input.value.strip())
                selected_layer_names = [cb.description for cb in state["layer_checkboxes"] if cb.value]
                upload_path = object_path_input.value.strip() or ""

                objects_metadata = await convert_duf_to_evo(
                    state["selected_file_path"], epsg_code, upload_path, manager, layers=selected_layer_names
                )

                if objects_metadata:
                    num_published = len(objects_metadata) if isinstance(objects_metadata, list) else 1
                    status_message.value = f"<div style='color:green;font-weight:600'>✓ Published {num_published} object(s) successfully</div>"
                    obj = objects_metadata[0] if isinstance(objects_metadata, list) else objects_metadata
                    workspace_url = build_portal_url(obj)
                    workspace_link.value = f'<a href="{workspace_url}" target="_blank">Open Evo workspace</a>'
                else:
                    status_message.value = (
                        "<div style='color:orange;font-weight:600'>⚠ No objects were converted.</div>"
                    )
                return objects_metadata

            await run_with_retry(task, status_message)

        run_timed_conversion(
            event_loop,
            timer_label,
            status_message,
            workspace_link,
            [convert_button, select_button, epsg_input, object_path_input],
            do_convert,
        )

    convert_button.on_click(on_convert_click)

    ui = widgets.VBox(
        [file_selection_box, read_layers_section, layer_selection_section, advanced_box, convert_section],
        layout=widgets.Layout(margin="0px"),
    )
    return ui
