import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
import os

class ImportFBXOperator(Operator, ImportHelper):
    """Operator to import an FBX file into a new collection called 'kn5'"""
    bl_idname = "import_scene.fbx_kn5"
    bl_label = "Import FBX into 'kn5' Collection"
    bl_description = "Import kn5 fbx file into blender. Be sure to leave the imported objects in the created collection"
    filename_ext = ".fbx"
    filter_glob: bpy.props.StringProperty(default="*.fbx", options={'HIDDEN'})

    def execute(self, context):
        # Get the file path
        fbx_file_path = self.filepath

        # Check if the file exists
        if not os.path.exists(fbx_file_path):
            self.report({'ERROR'}, "File not found.")
            return {'CANCELLED'}

        # Create the 'kn5' collection if it doesn't already exist
        collection_name = "kn5"
        if collection_name not in bpy.data.collections:
            kn5_collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(kn5_collection)
        else:
            kn5_collection = bpy.data.collections[collection_name]

        # Import the FBX file
        bpy.ops.import_scene.fbx(filepath=fbx_file_path)

        # Move the imported objects to the 'kn5' collection
        imported_objects = [obj for obj in bpy.context.selected_objects]
        for obj in imported_objects:
            # Unlink from the current collection and link to 'kn5'
            bpy.context.collection.objects.unlink(obj)
            kn5_collection.objects.link(obj)

        self.report({'INFO'}, f"FBX file '{os.path.basename(fbx_file_path)}' imported into 'kn5' collection.")
        return {'FINISHED'}

# Register the operator
def register():
    bpy.utils.register_class(ImportFBXOperator)

def unregister():
    bpy.utils.unregister_class(ImportFBXOperator)

# Add a callable function to import FBX using the operator
def import_fbx_to_collection(context):
    bpy.ops.import_scene.fbx_kn5('INVOKE_DEFAULT')
