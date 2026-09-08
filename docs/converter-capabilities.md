# Converter Capability Matrix
This page is generated from `converter-capabilities.json`.
Generated (UTC): 2026-09-08 21:55:00
| Converter | Status | Import | Export | Source Formats | Evo Objects (Import) | Key Limitations |
|---|---|---|---|---|---|---|
| DUF | implemented | Yes | No | .duf | TriangleMesh, LineSegments | Some DUF geometry types are not supported., TriangleMesh: Per-face colour data is ignored on import., TriangleMesh: Negative face index visibility semantics are ignored; all faces are forced visible. |
| GOCAD | implemented | Yes | No | .vo | Regular3DGrid | Current converter path is focused on voxel grid data. |
| Image | implemented | Yes | No | .jpeg, .jpg, .png, .tif, .tiff, .bmp, .gif | Regular2DGrid | No Evo-to-image exporter is currently provided. |
| OBJ | implemented | Yes | Yes | .obj | TriangleMesh | Export currently supports only triangle-mesh objects., TinyOBJ support depends on a pinned Git installation path., TriangleMesh: Texture/material data on import is ignored., TriangleMesh: Export does not include texture/material payloads. |
| OMF | implemented | Yes | Yes | .omf | Pointset, TriangleMesh, LineSegments, BlockSync block model metadata | Some geometry types and geoscience object types are not yet supported., LineSegments: OMF LineSet is mapped to LineSegments; other interpretations such as drillholes or wireframe mesh are not produced. |
| RESQML | implemented | Yes | No | .epc, .xml | UnstructuredHexGrid, TriangleMesh, DownholeIntervals | Large grid conversion can be skipped when estimated corner_points memory exceeds configured threshold., UnstructuredHexGrid: Grid properties indexed by non-cell elements (e.g. nodes or faces) are ignored., UnstructuredHexGrid: Grid properties of unknown or unsupported type are ignored. |
| SHP | implemented | Yes | No | .shp, .shx, .dbf, .prj | TriangleMesh | TriangleMesh: Ring-based multipatch parts (OUTER_RING, INNER_RING, etc.) are not supported., TriangleMesh: NULL shapes (records with associated data but no geometry) are discarded. |
| UBC | implemented | Yes | No | .msh, .mod, .sus, .den | Tensor3DGrid | Requires exactly one .msh mesh file per conversion call. |
| VTK | implemented | Yes | No | .vti, .vtr, .vtu, .vtm, .xml | Regular3DGrid, RegularMasked3DGrid, Tensor3DGrid, UnstructuredTetGrid, UnstructuredHexGrid, UnstructuredGrid | Only XML VTK files are supported., VTK data object types outside the supported set are skipped with a warning., Individual grid conversion errors are caught per-grid and skipped. |
| XYZ | implemented | Yes | No | .xyz, .XYZ | Pointset | No Evo-to-XYZ exporter is currently provided., For multi-column Geosoft files, behavior depends on x_index/y_index/z_index/data_index selection. |

## Detailed Capabilities
### DUF
- Package: `evo-data-converters-duf`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `No`
- Source formats: .duf
- Platform/runtime notes: Windows only, Requires Deswik Spatial and compatible .NET runtime
- Import source types: Polyface, Polyline
- Evo objects produced: TriangleMesh, LineSegments
- Evo objects export supports: -
- Limitations: Some DUF geometry types are not supported., TriangleMesh: Per-face colour data is ignored on import., TriangleMesh: Negative face index visibility semantics are ignored; all faces are forced visible.

### GOCAD
- Package: `evo-data-converters-gocad`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `No`
- Source formats: .vo
- Platform/runtime notes: Cross-platform (Python)
- Import source types: GOCAD voxel grid
- Evo objects produced: Regular3DGrid
- Evo objects export supports: -
- Limitations: Current converter path is focused on voxel grid data.

### Image
- Package: `evo-data-converters-image`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `No`
- Source formats: .jpeg, .jpg, .png, .tif, .tiff, .bmp, .gif
- Platform/runtime notes: Cross-platform (Python)
- Import source types: Grayscale images, Colour images
- Evo objects produced: Regular2DGrid
- Evo objects export supports: -
- Limitations: No Evo-to-image exporter is currently provided.

### OBJ
- Package: `evo-data-converters-obj`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `Yes`
- Source formats: .obj
- Platform/runtime notes: Cross-platform (Python), TinyOBJ backend requires optional extra installation
- Import source types: Polygon mesh (via trimesh or tinyobj backend)
- Evo objects produced: TriangleMesh
- Evo objects export supports: TriangleMesh (schema classification objects/triangle-mesh, major version 2)
- Limitations: Export currently supports only triangle-mesh objects., TinyOBJ support depends on a pinned Git installation path., TriangleMesh: Texture/material data on import is ignored., TriangleMesh: Export does not include texture/material payloads.

### OMF
- Package: `evo-data-converters-omf`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `Yes`
- Source formats: .omf
- Platform/runtime notes: Cross-platform with native build tool requirements
- Import source types: OMF PointSet, OMF Surface, OMF LineSet, OMF BlockModel
- Evo objects produced: Pointset, TriangleMesh, LineSegments, BlockSync block model metadata
- Evo objects export supports: TriangleMesh, LineSegments, Pointset, BlockSync block models
- Limitations: Some geometry types and geoscience object types are not yet supported., LineSegments: OMF LineSet is mapped to LineSegments; other interpretations such as drillholes or wireframe mesh are not produced.

### RESQML
- Package: `evo-data-converters-resqml`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `No`
- Source formats: .epc, .xml
- Platform/runtime notes: Cross-platform (Python)
- Import source types: IjkGridRepresentation, TriangulatedSetRepresentation, WellboreTrajectoryRepresentation
- Evo objects produced: UnstructuredHexGrid, TriangleMesh, DownholeIntervals
- Evo objects export supports: -
- Limitations: Large grid conversion can be skipped when estimated corner_points memory exceeds configured threshold., UnstructuredHexGrid: Grid properties indexed by non-cell elements (e.g. nodes or faces) are ignored., UnstructuredHexGrid: Grid properties of unknown or unsupported type are ignored.

### SHP
- Package: `evo-data-converters-shp`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `No`
- Source formats: .shp, .shx, .dbf, .prj
- Platform/runtime notes: Cross-platform (Python)
- Import source types: Multipatch shapefiles without rings
- Evo objects produced: TriangleMesh
- Evo objects export supports: -
- Limitations: TriangleMesh: Ring-based multipatch parts (OUTER_RING, INNER_RING, etc.) are not supported., TriangleMesh: NULL shapes (records with associated data but no geometry) are discarded.

### UBC
- Package: `evo-data-converters-ubc`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `No`
- Source formats: .msh, .mod, .sus, .den
- Platform/runtime notes: Cross-platform (Python)
- Import source types: UBC mesh + numeric property files
- Evo objects produced: Tensor3DGrid
- Evo objects export supports: -
- Limitations: Requires exactly one .msh mesh file per conversion call.

### VTK
- Package: `evo-data-converters-vtk`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `No`
- Source formats: .vti, .vtr, .vtu, .vtm, .xml
- Platform/runtime notes: Cross-platform (Python)
- Import source types: vtkImageData / vtkUniformGrid / vtkStructuredPoints, vtkRectilinearGrid, vtkUnstructuredGrid
- Evo objects produced: Regular3DGrid, RegularMasked3DGrid, Tensor3DGrid, UnstructuredTetGrid, UnstructuredHexGrid, UnstructuredGrid
- Evo objects export supports: -
- Limitations: Only XML VTK files are supported., VTK data object types outside the supported set are skipped with a warning., Individual grid conversion errors are caught per-grid and skipped.

### XYZ
- Package: `evo-data-converters-xyz`
- Status: `implemented`
- Import supported: `Yes`
- Export supported: `No`
- Source formats: .xyz, .XYZ
- Platform/runtime notes: Cross-platform (Python)
- Import source types: Points, Binary, Geochemistry (comma/space), Geosoft Binary/Triplet variants
- Evo objects produced: Pointset
- Evo objects export supports: -
- Limitations: No Evo-to-XYZ exporter is currently provided., For multi-column Geosoft files, behavior depends on x_index/y_index/z_index/data_index selection.

