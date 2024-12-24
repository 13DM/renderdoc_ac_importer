import bpy
import logging

# Set up logging
logger = logging.getLogger("MeshRenamerReparenter")

def rename_and_reparent_meshes(debug_flag):
    """
    Renames each mesh in the 'kn5' collection to the name of its parent and reparents the mesh to its grandparent, keeping transforms.
    Deletes the 'Unused_Parents' collection if debug mode is off.
    """
    kn5_collection = bpy.data.collections.get('kn5')
    if not kn5_collection:
        logger.error("No 'kn5' collection found.")
        return
    
    # Create a collection to store the parent objects for later deletion
    parents_collection_name = "Unused_Parents"
    if parents_collection_name not in bpy.data.collections:
        parents_collection = bpy.data.collections.new(parents_collection_name)
        bpy.context.scene.collection.children.link(parents_collection)
    else:
        parents_collection = bpy.data.collections[parents_collection_name]

    for obj in kn5_collection.objects:
        if obj.type != 'MESH' or not obj.parent:
            continue

        parent = obj.parent
        grandparent = parent.parent

        # Rename the mesh to the parent's name
        original_name = obj.name
        obj.name = parent.name
        logger.info(f"Renamed object '{original_name}' to '{parent.name}'.")

        # Store the current world matrix
        world_matrix = obj.matrix_world.copy()

        # Parent the mesh to the grandparent while keeping transforms
        obj.parent = grandparent
        obj.matrix_world = world_matrix

        # Move the parent to the 'Unused_Parents' collection for later deletion
        if parent.name not in parents_collection.objects:
            parents_collection.objects.link(parent)
        if parent.name in kn5_collection.objects:
            kn5_collection.objects.unlink(parent)

    # If debug mode is off, delete the 'Unused_Parents' collection and its objects
    if not debug_flag:
        # Select all objects in the 'Unused_Parents' collection
        for obj in parents_collection.objects:
            obj.select_set(True)
        # Delete the objects
        bpy.ops.object.delete()
        # Remove the collection
        bpy.data.collections.remove(parents_collection)
        logger.info("'Unused_Parents' collection and its objects deleted.")

    logger.info("Renaming and reparenting completed.")

# Define the new operator for renaming and reparenting meshes
class OBJECT_OT_RenameAndReparentMeshes(bpy.types.Operator):
    bl_idname = "object.rename_and_reparent_meshes"
    bl_label = "Rename & Reparent Meshes"
    bl_description = "Renames each mesh in the 'kn5' collection to its parent's name and reparents it to the grandparent, keeping transforms."

    def execute(self, context):
        # Ensure we are in object mode
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        debug_flag = context.scene.debug_flag  # Read the debug flag from the scene
        rename_and_reparent_meshes(debug_flag)
        self.report({'INFO'}, "Renaming and reparenting completed.")
        return {'FINISHED'}

# Register the operator
def register():
    bpy.utils.register_class(OBJECT_OT_RenameAndReparentMeshes)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_RenameAndReparentMeshes)
