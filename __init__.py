bl_info = {
    "name": "RenderDoc Asset Importer",
    "author": "Dad",
    "version": (1, 2, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > RDAC"
}

import bpy
import os
from .rdc_importer import import_meshes_from_rdc # RD capture importer logic
from .fbx_importer import ImportFBXOperator  # Import the FBX operator
from .mesh_matcher import MatchMeshesOperator, ApplyMaterialsConstraintsOperator, HideConstraintObjectsOperator, ShowConstraintObjectsOperator, ManualMatchOperator # Matching and materials logic
from .mesh_renamer import OBJECT_OT_RenameAndReparentMeshes  # Import the new renaming and reparenting operator
from .ini_processor import main_ini_processer  # Import the main function for INI processing

# Operator for reading and processing the INI file
class OBJECT_OT_ReadINI(bpy.types.Operator):
    bl_idname = "object.read_ini"
    bl_label = "Read and Process INI"
    bl_description = "Reads an INI file, applies material settings, and exports textures"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        # Call the main INI processor function with the selected file path
        main_ini_processer(self.filepath)
        self.report({'INFO'}, 'INI file processed successfully.')
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# RenderDoc Asset Importer panel
class RENDERDOC_PT_ACImporter(bpy.types.Panel):
    bl_label = "RenderDoc Asset Importer"
    bl_idname = "RENDERDOC_PT_ac_importer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RDAC'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # RDC file selection
        layout.label(text="RDC Importer:")
        layout.prop(scene, "rdc_file_path", text="RDC File")

        # Max action number input
        layout.prop(scene, "max_action_id", text="Max Action ID")
        
        # Min action number input (conditionally visible) based on the max action id
        # if not set, then display the range provider to select multiple ranges
        if scene.max_action_id >= 0:
            layout.prop(scene, "min_action_id", text="Min Action ID")
        else:
            layout.prop(scene, "manual_action_ranges", text="Action Ranges")

        # Button to run the import process
        layout.separator()
        layout.operator("renderdoc_ac_importer.run_import", text="Import RDC File")

        # FBX Importer section
        layout.separator()
        layout.label(text="FBX Importer:")
        layout.operator("import_scene.fbx_kn5", text="Import FBX")

        # Mesh Matching section
        layout.separator()
        layout.label(text="Mesh Matching:")
        layout.prop(scene, "matching_threshold", text="Matching Threshold")
        layout.operator("mesh_matcher.match_meshes", text="Match Meshes (AUTO)")
        layout.operator("mesh_matcher.manual_match", text="Match Meshes (MANUAL)")
        layout.separator()
        layout.operator("mesh_matcher.hide_constraint_objects", text="Hide Objects")
        layout.operator("mesh_matcher.show_constraint_objects", text="Show Objects")

        # Apply Materials and Constraints
        layout.separator()
        layout.label(text="Materials & Constraints:")
        layout.prop(scene, "debug_flag", text="Debug Mode")
        
        # Mesh Renaming & Reparenting section
        layout.separator()
        layout.label(text="Mesh Renaming & Reparenting:")
        layout.operator("object.rename_and_reparent_meshes", text="Rename & Reparent Meshes")
        layout.operator("mesh_matcher.apply_materials_constraints", text="Apply Materials & Constraints")
        
        layout.separator()
        layout.label(text="INI File Processing:")
        layout.operator("object.read_ini", text="Process INI File")

# Operator to run the import process for the Renderdoc file
class RENDERDOC_OT_RunImport(bpy.types.Operator):
    bl_idname = "renderdoc_ac_importer.run_import"
    bl_label = "Run RDC Import"
    bl_description = "Import RenderDoc Capture file into Blender."

    def execute(self, context):
        scene = context.scene
        rdc_file_path = scene.rdc_file_path
        min_action_id = scene.min_action_id if scene.max_action_id >= 0 else None
        max_action_id = scene.max_action_id
        manual_ranges = scene.manual_action_ranges if max_action_id == -1 else ""

        if not rdc_file_path:
            self.report({'ERROR'}, "Please select an RDC file.")
            return {'CANCELLED'}

        # Call the mane function to bring the files in
        import_meshes_from_rdc(rdc_file_path, min_action_id, max_action_id, manual_ranges)
        return {'FINISHED'}

# Function to handle file selection
def select_rdc_file(self, context):
    context.scene.rdc_file_path = bpy.path.abspath(self.filepath)

# Properties for the panel
def init_properties():
    bpy.types.Scene.rdc_file_path = bpy.props.StringProperty(
        name="RDC File",
        description="Path to the RenderDoc capture file. This also controls the log file, and texture export location",
        default="",
        maxlen=1024,
        subtype='FILE_PATH',
        update=select_rdc_file
    )

    bpy.types.Scene.min_action_id = bpy.props.IntProperty(
        name="Min Action ID",
        description="Minimum action ID to process. Can only be set when Maximum Action ID is set",
        default=0,
        min=0
    )

    bpy.types.Scene.max_action_id = bpy.props.IntProperty(
        name="Max Action ID",
        description="Maximum action ID to process. Set to -1 for no limit. Will hide the lower limit when set to -1",
        default=-1,
        min=-1
    )

    bpy.types.Scene.manual_action_ranges = bpy.props.StringProperty(
        name="Manual Ranges",
        description="Specify action ranges (e.g., 1-200;500-685).",
        default=""
    )

    bpy.types.Scene.matching_threshold = bpy.props.FloatProperty(
        name="Matching Threshold",
        description="Threshold for matching RenderDoc meshes to the loaded kn5. The lower the number, the more accurate the matches should be. Set higher for less accuracy but more matches",
        default=0.5,
        min=0.00001
    )

    bpy.types.Scene.debug_flag = bpy.props.BoolProperty(
        name="Debug Flag",
        description="If enabled prevents deletion of create or move actions. If disabled actions will delete objects where needed. Be sure to save before disabling",
        default=False
    )

# Remove properties
def clear_properties():
    del bpy.types.Scene.rdc_file_path
    del bpy.types.Scene.min_action_id
    del bpy.types.Scene.max_action_id
    del bpy.types.Scene.matching_threshold
    del bpy.types.Scene.debug_flag
    del bpy.types.Scene.manual_action_ranges

# Register and Unregister functions
classes = [
    RENDERDOC_PT_ACImporter,
    RENDERDOC_OT_RunImport,
    ImportFBXOperator,  # Register the FBX import operator
    MatchMeshesOperator,
    ApplyMaterialsConstraintsOperator,
    OBJECT_OT_RenameAndReparentMeshes,  # Register the new renaming and reparenting operator
    OBJECT_OT_ReadINI,
    HideConstraintObjectsOperator,  
    ShowConstraintObjectsOperator,
    ManualMatchOperator,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    init_properties()

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    clear_properties()

if __name__ == "__main__":
    register()
