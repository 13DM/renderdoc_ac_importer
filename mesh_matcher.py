import bpy
import logging
import mathutils

# Set up logging
logger = logging.getLogger("MeshMatcher")

def get_vertex_count_and_center(obj):
    """
    Returns the vertex count and the approximate center of vertices.
    """
    vertices = [v.co for v in obj.data.vertices]
    vertex_count = len(vertices)
    
    # Calculate approximate center by averaging vertex positions
    avg_x = sum(v.x for v in vertices) / vertex_count
    avg_y = sum(v.y for v in vertices) / vertex_count
    avg_z = sum(v.z for v in vertices) / vertex_count
    center = mathutils.Vector((avg_x, avg_y, avg_z))
    
    return vertex_count, center

def apply_constraints_and_store_data(collection):
    """
    Applies the 'Copy Transforms' constraint to each object in the specified collection and stores
    the original names and target names for reparenting and renaming later. After applying, the
    object is re-parented to the target while keeping the original transform.
    """
    object_data = {}  # Dictionary to store references between RDC and target KN5 objects
    
    # Ensure we are in Object Mode
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    for obj in collection.objects:
        if obj.type == 'MESH':
            # Check if the object has a 'Copy Transforms' constraint
            copy_transform_constraint = None
            for constraint in obj.constraints:
                if constraint.type == 'COPY_TRANSFORMS' and constraint.name == "Copy Transforms":
                    copy_transform_constraint = constraint
                    break
            
            # Only proceed if the 'Copy Transforms' constraint exists
            if copy_transform_constraint:
                target_obj = copy_transform_constraint.target
                if target_obj:
                    # Store the relationship between the RDC object and the KN5 target
                    object_data[obj.name] = {
                        "rdc_object": obj,
                        "target_object": target_obj,
                        "original_name": obj.name,
                        "target_name": target_obj.name,
                        "target_parent": target_obj.parent,
                    }
                    
                    # Make the object active and select it to apply the constraint
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)
                    
                    # Apply the "Copy Transforms" constraint using the correct operator call
                    bpy.ops.constraint.apply(constraint="Copy Transforms", owner='OBJECT')
                    
                    # Deselect the object after applying
                    obj.select_set(False)
                    
                    # Remove the constraint from the object if it still exists
                    if "Copy Transforms" in obj.constraints:
                        obj.constraints.remove(copy_transform_constraint)
                    
                    logger.info(f"Applied 'Copy Transforms' constraint for {obj.name} using target {target_obj.name}")
                else:
                    logger.warning(f"No target found for 'Copy Transforms' constraint on {obj.name}")
            else:
                logger.info(f"No 'Copy Transforms' constraint found on {obj.name}, skipping.")
    
    return object_data


def reparent_and_rename_objects(object_data, debug_flag):
    """
    Reparents, renames, adjusts materials, and removes objects from the RDC collection after processing.
    """
    kn5_collection = bpy.data.collections.get('kn5')
    rdc_collection = bpy.data.collections.get('RDC')  # Get the RDC collection

    if not kn5_collection:
        logger.error("KN5 collection not found.")
        return
    
    if not rdc_collection:
        logger.error("RDC collection not found.")
        return

    for data in object_data.values():
        obj = data["rdc_object"]
        target_obj = data["target_object"]
        target_name = data["target_name"]
        target_parent = data["target_parent"]

        try:
            # Check if the target object is valid before proceeding
            if target_obj and target_obj.data and target_obj.data.materials:
                kn5_material = target_obj.data.materials[0]  # Assume the first material is the primary one
                kn5_material_name = kn5_material.name
                
                if not kn5_material_name.endswith("_old"):
                    # Rename KN5 material by appending "_old"
                    new_kn5_material_name = kn5_material_name + "_old"
                    if new_kn5_material_name not in bpy.data.materials:
                        kn5_material.name = new_kn5_material_name
                    else:
                        kn5_material = bpy.data.materials[new_kn5_material_name]
                    
                    # Rename RDC material to match the original KN5 material name
                    if obj.data and obj.data.materials:
                        rdc_material = obj.data.materials[0]
                        rdc_material.name = kn5_material_name
                    
                    logger.info(f"Renamed {obj.name} material to '{kn5_material_name}' and {target_obj.name} material to '{new_kn5_material_name}'")
                
                else:
                    # If KN5 material already has "_old", find the non-"_old" version and assign it to RDC
                    original_material_name = kn5_material_name[:-4]  # Remove "_old" suffix
                    if original_material_name in bpy.data.materials:
                        obj.data.materials[0] = bpy.data.materials[original_material_name]
                        logger.info(f"Assigned original material '{original_material_name}' to {obj.name} instead of renaming.")

        except ReferenceError:
            logger.warning(f"Target object '{target_name}' is no longer valid and has been skipped.")

        # Rename the RDC object to the target's original name
        obj.name = target_name

        # Reparent the RDC object to the target's parent, keeping the transform
        obj.parent = target_parent
        obj.matrix_parent_inverse = target_parent.matrix_world.inverted() if target_parent else obj.matrix_parent_inverse

        # Add the RDC object to the KN5 collection if it's not already there
        if obj.name not in kn5_collection.objects:
            kn5_collection.objects.link(obj)
        
        # Remove the RDC object from the RDC collection
        if obj.name in rdc_collection.objects:
            rdc_collection.objects.unlink(obj)

        # Handle the debug flag for hiding or deleting the target object
        if debug_flag:
            target_obj.hide_viewport = True
        else:
            # Delete only the target object
            try:
                target_obj.select_set(True)
                bpy.context.view_layer.objects.active = target_obj
                bpy.ops.object.delete()
                logger.info(f"Deleted the target object '{target_name}'.")
            except ReferenceError:
                logger.warning(f"Failed to delete target object '{target_name}', as it no longer exists.")

def manual_add_copy_transforms_constraint():
    selected_objects = bpy.context.selected_objects
    active_object = bpy.context.active_object

    # Check if exactly 2 objects are selected
    if len(selected_objects) != 2:
        print("Please select exactly two objects.")
        return

    # Ensure the active object is part of the selection
    if active_object not in selected_objects:
        print("Active object must be one of the selected objects.")
        return

    # Determine the target object
    target_object = [obj for obj in selected_objects if obj != active_object][0]

    # Add Copy Transforms constraint to the active object
    constraint = active_object.constraints.new(type='COPY_TRANSFORMS')
    constraint.name = "Copy Transforms"
    constraint.target = target_object

    print(f"Copy Transforms constraint applied: {active_object.name} -> {target_object.name}")


def main_apply_materials_and_constraints(debug_flag):
    """
    Main function to apply constraints, reparent, and rename objects.
    """
    # Get the RDC collection
    rdc_collection = bpy.data.collections.get('RDC')
    if not rdc_collection:
        logger.error("RDC collection not found.")
        return

    # Apply constraints and store references for reparenting and renaming
    object_data = apply_constraints_and_store_data(rdc_collection)
    
    # Reparent and rename objects
    reparent_and_rename_objects(object_data, debug_flag)


def find_objects_with_multiple_constraints(collection, constraint_type='COPY_TRANSFORMS'):
    """
    Loops through all objects in the specified collection and checks if there are multiple
    constraints of the specified type. Returns a list of objects with multiple constraints.
    """
    objects_with_multiple_constraints = []

    for obj in collection.objects:
        # Count constraints of the specified type
        constraint_count = sum(1 for constraint in obj.constraints if constraint.type == constraint_type)

        # If there are multiple constraints, add the object to the list
        if constraint_count > 1:
            objects_with_multiple_constraints.append(obj)
            logger.warning(f"Object '{obj.name}' has {constraint_count} '{constraint_type}' constraints.")

    return objects_with_multiple_constraints


def match_meshes(collection1, collection2, threshold):
    """
    Matches meshes from collection1 (corrupted) to collection2 (corrected).
    Ensures multiple constraints are avoided and retries for alternate matches.
    """
    unmatched_meshes = []
    used_objects = set()  # Track objects that already have constraints

    for obj1 in collection1.objects:
        if obj1.type == 'MESH':
            obj1_vertex_count, obj1_center = get_vertex_count_and_center(obj1)
            best_match = None
            best_distance = float('inf')

            # Loop through second collection to find best match
            for obj2 in collection2.objects:
                if obj2.type == 'MESH' and obj2 not in used_objects:
                    obj2_vertex_count, obj2_center = get_vertex_count_and_center(obj2)

                    if obj1_vertex_count == obj2_vertex_count:
                        # Calculate the distance between centers
                        distance = (obj1_center - obj2_center).length

                        # Check if the distance is within the threshold and better than current best
                        if distance <= threshold and distance < best_distance:
                            # Check if this obj2 already has a matching constraint
                            constraint_exists = False
                            for c in obj2.constraints:
                                if c.type == 'COPY_TRANSFORMS' and c.target == obj1:
                                    constraint_exists = True
                                    break

                            if not constraint_exists:
                                best_match = obj2
                                best_distance = distance

            # If we found a best match, apply the constraint
            if best_match:
                constraint = best_match.constraints.new(type='COPY_TRANSFORMS')
                constraint.target = obj1
                used_objects.add(best_match)  # Mark this object as used
                logger.info(f"Matched {obj1.name} to {best_match.name} with distance {best_distance:.4f}.")
            else:
                unmatched_meshes.append(obj1.name)
                logger.warning(f"No match found for {obj1.name}.")

    # Check for multiple constraints post-application
    rdc_collection = bpy.data.collections.get('RDC')
    if rdc_collection:
        problematic_objects = find_objects_with_multiple_constraints(rdc_collection)
        if problematic_objects:
            logger.warning(f"Objects with multiple constraints: {[obj.name for obj in problematic_objects]}")

    return unmatched_meshes


# Function to hide objects with constraints and their targets
def hide_objects_with_constraints():
    # Ensure the collection named "RDC" exists
    rdc_collection = bpy.data.collections.get("RDC")
    if not rdc_collection:
        print("Collection named 'RDC' not found.")
        return

    # Iterate through all objects in the RDC collection
    for obj in rdc_collection.objects:
        # Check if the object has constraints
        for constraint in obj.constraints:
            if constraint.type == 'COPY_TRANSFORMS':  # Adjust constraint type as needed
                target = constraint.target
                if target:
                    # Hide the object and its target from the viewport
                    obj.hide_viewport = True
                    target.hide_viewport = True
                    print(f"Hid {obj.name} and its target {target.name}")
                else:
                    print(f"Constraint on {obj.name} has no target.")
    print("Completed hiding objects with constraints and their targets.")


# Function to make objects with constraints and their targets visible
def make_objects_with_constraints_visible():
    # Ensure the collection named "RDC" exists
    rdc_collection = bpy.data.collections.get("RDC")
    if not rdc_collection:
        print("Collection named 'RDC' not found.")
        return

    # Iterate through all objects in the RDC collection
    for obj in rdc_collection.objects:
        # Check if the object has constraints
        for constraint in obj.constraints:
            if constraint.type == 'COPY_TRANSFORMS':  # Adjust constraint type as needed
                target = constraint.target
                if target:
                    # Make the object and its target visible in the viewport
                    obj.hide_viewport = False
                    target.hide_viewport = False
                    print(f"Made {obj.name} and its target {target.name} visible")
                else:
                    print(f"Constraint on {obj.name} has no target.")
    print("Completed making objects with constraints and their targets visible.")

def rename_objects_with_suffix():
    """
    Goes through all objects in the scene and renames objects ending with '.001' if
    the name without '.001' does not exist.
    """
    for obj in bpy.data.objects:
        # Check if the object name ends with ".001"
        if obj.name.endswith(".001"):
            # Generate the name without ".001"
            base_name = obj.name[:-4]  # Remove the last 4 characters (".001")

            # Check if any object with the base name exists
            if not bpy.data.objects.get(base_name):
                # Rename the object to the base name
                old_name = obj.name
                obj.name = base_name
                print(f"Renamed '{old_name}' to '{obj.name}'")
            else:
                print(f"Skipped renaming '{obj.name}', '{base_name}' already exists.")


class MatchMeshesOperator(bpy.types.Operator):
    bl_idname = "mesh_matcher.match_meshes"
    bl_label = "Match Meshes"
    bl_description = "Used to match meshes from the RDC file to the imported KN5 file. This can take some time, please be sure to let the action complete or check console for progress"

    def execute(self, context):
        scene = context.scene
        collection1 = bpy.data.collections.get('kn5')
        collection2 = bpy.data.collections.get('RDC')
        threshold = scene.matching_threshold

        if collection1 and collection2:
            unmatched = match_meshes(collection1, collection2, threshold)
            
            if unmatched:
                logger.error(f"Unmatched objects: {', '.join(unmatched)}")
            else:
                self.report({'INFO'}, "Mesh matching completed successfully.")
        else:
            logger.error("One or both collections are missing.")
            self.report({'ERROR'}, "One or both collections are missing.")

        return {'FINISHED'}

class ApplyMaterialsConstraintsOperator(bpy.types.Operator):
    bl_idname = "mesh_matcher.apply_materials_constraints"  # Retained the original name
    bl_label = "Apply Materials and Constraints"

    def execute(self, context):
        debug_flag = context.scene.debug_flag  # Read the debug flag from the scene
        main_apply_materials_and_constraints(debug_flag)
        rename_objects_with_suffix()
        self.report({'INFO'}, "Materials and constraints applied successfully.")
        return {'FINISHED'}


class ManualMatchOperator(bpy.types.Operator):
    bl_idname = "mesh_matcher.manual_match"  # Retained the original name
    bl_label = "Manual Match Meshes"

    def execute(self, context):
        manual_add_copy_transforms_constraint()
        self.report({'INFO'}, "Matched objects manually.")
        return {'FINISHED'}

class HideConstraintObjectsOperator(bpy.types.Operator):
    bl_idname = "mesh_matcher.hide_constraint_objects"
    bl_label = "Hide Constraint Objects"
    bl_description = "Used to hide objects from the RDC collection"

    def execute(self, context):
        scene = context.scene
        
        if bpy.data.collections.get('RDC'):
            hide_objects_with_constraints()
            
            logger.info(f"Objects with constraints were hidden.")
            self.report({'INFO'}, "Constraint objects hidden.")

        return {'FINISHED'}

class ShowConstraintObjectsOperator(bpy.types.Operator):
    bl_idname = "mesh_matcher.show_constraint_objects"
    bl_label = "Show Constraint Objects"
    bl_description = "Used to show objects from the RDC collection"

    def execute(self, context):
        scene = context.scene
        
        if bpy.data.collections.get('RDC'):
            make_objects_with_constraints_visible()
            
            logger.info(f"Objects with constraints were made visible.")
            self.report({'INFO'}, "Constraint objects are visible.")

        return {'FINISHED'}

def register():
    bpy.utils.register_class(MatchMeshesOperator)
    bpy.utils.register_class(ApplyMaterialsConstraintsOperator)
    bpy.utils.register_class(HideConstraintObjectsOperator)
    bpy.utils.register_class(ShowConstraintObjectsOperator)
    bpy.utils.register_class(ManualMatchOperator)
    bpy.types.Scene.debug_flag = bpy.props.BoolProperty(
        name="Debug Flag",
        description="If enabled, hides the KN5 object. If disabled, deletes the KN5 object.",
        default=False
    )

def unregister():
    bpy.utils.unregister_class(MatchMeshesOperator)
    bpy.utils.unregister_class(ApplyMaterialsConstraintsOperator)
    bpy.utils.unregister_class(HideConstraintObjectsOperator)
    bpy.utils.unregister_class(ShowConstraintObjectsOperator)
    bpy.utils.unregister_class(ManualMatchOperator)
    del bpy.types.Scene.debug_flag

if __name__ == "__main__":
    register()
