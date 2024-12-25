import sys
import os
import logging
import bpy
import struct

# Attempt to import renderdoc, if not found, try to add the external libs directory to sys.path and environment variables
try:
    import renderdoc as rd
except ImportError as original_error:
    # Get the current file's directory
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    external_libs_dir = os.path.join(addon_dir, 'external_libs', 'renderdoc')

    # Add the external_libs_dir to the DLL search path (Windows-only)
    if os.name == 'nt':
        if os.path.exists(external_libs_dir):
            try:
                # Add the directory containing renderdoc.dll to the DLL search path
                os.add_dll_directory(external_libs_dir)
                print(f"Added {external_libs_dir} to DLL search path.")

                # Add the external_libs_dir to the PATH environment variable for DLL loading
                os.environ['PATH'] = external_libs_dir + os.pathsep + os.environ.get('PATH', '')
            except Exception as e:
                print(f"Failed to add DLL directory: {e}")
                raise ImportError(f"Failed to add {external_libs_dir} to the DLL directory. Error: {e}")
        else:
            raise ImportError(f"Could not find 'external_libs/renderdoc' directory at: {external_libs_dir}")

    # Add the external_libs/renderdoc directory to the system path if not already present
    if external_libs_dir not in sys.path:
        sys.path.insert(0, external_libs_dir)

    # Try importing renderdoc again
    try:
        import renderdoc as rd
    except ImportError as e:
        # Detailed debug output
        print(f"sys.path: {sys.path}")
        print(f"os.environ['PATH']: {os.environ.get('PATH')}")
        print(f"Tried to import renderdoc from: {external_libs_dir}")
        raise ImportError(f"Could not import 'renderdoc' module. Make sure 'renderdoc' is installed or present in 'external_libs/renderdoc' directory.") from e


MAX_VERTICES = 150000
MAX_INDICES = 450000

# Helper function for logging setup
def setup_logging(rdc_file_path):
    log_file_path = os.path.join(os.path.dirname(rdc_file_path), 'mesh_import_log.txt')
    if not logging.getLogger().hasHandlers():
        class FlushFileHandler(logging.FileHandler):
            def emit(self, record):
                super().emit(record)
                self.flush()

        logging.basicConfig(level=logging.DEBUG, filename=log_file_path, filemode='w', format='%(message)s')
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(console_handler)

        file_handler = FlushFileHandler(log_file_path)
        file_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(file_handler)

# Save texture with slot name
def save_texture(controller, texture_id, slot_name, rdc_file_path):
    texture = next((tex for tex in controller.GetTextures() if tex.resourceId == texture_id), None)

    if not texture:
        logging.error(f"Texture {texture_id} not found.")
        return False

    if texture.width == 1 and texture.height == 1:
        logging.info(f"Skipping 1x1 texture with ResourceId: {texture_id}.")
        return False

    save_data = rd.TextureSave()
    save_data.resourceId = texture.resourceId
    save_data.destType = rd.FileType.DDS
    save_data.comp.blackPoint = 0.0
    save_data.comp.whitePoint = 1.0
    save_data.alpha = rd.AlphaMapping.Preserve
    save_data.mip = 0
    save_data.slice.sliceIndex = 0

    texture_id_numeric = int(str(texture_id).split("::")[-1])
    output_dir = os.path.join(os.path.dirname(rdc_file_path), os.path.splitext(os.path.basename(rdc_file_path))[0])
    os.makedirs(output_dir, exist_ok=True)

    # Use slot name in filename
    texture_filename = f"resourceFile_{texture_id_numeric}_{slot_name}.dds"
    texture_path = os.path.join(output_dir, texture_filename)

    if os.path.exists(texture_path):
        logging.info(f"Skipping texture save. File already exists: {texture_path}")
        return texture_path

    success = controller.SaveTexture(save_data, texture_path)
    if success:
        logging.info(f"Successfully saved texture to {texture_path}")
        return texture_path
    else:
        logging.error(f"Failed to save texture to {texture_path}.")
        return False

# Create or get material
def create_or_get_material(buffer_id):
    material_name = f"Material_{buffer_id}"
    material = bpy.data.materials.get(material_name)
    
    if not material:
        material = bpy.data.materials.new(name=material_name)
        material.use_nodes = True
        configure_ac_shader(material)
        logging.info(f"Created new material: {material_name}")
    else:
        logging.info(f"Using existing material: {material_name}")
    
    return material

def configure_ac_shader(material):
    if material.use_nodes:
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        
        # Clear existing nodes
        nodes.clear()

        # Create and set up all required nodes
        img_tex_nodes = []
        for i in range(8):
            img_tex_node = nodes.new(type='ShaderNodeTexImage')
            img_tex_node.name = f'Image Texture.{i:03}' if i > 0 else 'Image Texture'
            img_tex_node.location.x = -300 - (i // 3) * 300
            img_tex_node.location.y = 300 - (i % 3) * 300
            img_tex_node.width = 240
            img_tex_nodes.append(img_tex_node)

        # Create and position additional nodes as per provided setup
        normal_map_node = nodes.new(type='ShaderNodeNormalMap')
        normal_map_node.name = "Normal Map 1"
        normal_map_node.location = (10, -423)

        separate_color_node = nodes.new(type='ShaderNodeSeparateColor')
        separate_color_node.name = "TxtMap Separate Color"
        separate_color_node.location = (-200, -610)

        math1_node = nodes.new(type='ShaderNodeMath')
        math1_node.name = "TxtMap Math 1"
        math1_node.operation = 'MULTIPLY'
        math1_node.inputs[1].default_value = -1
        math1_node.location = (10, -610)

        math2_node = nodes.new(type='ShaderNodeMath')
        math2_node.name = "TxtMap Math 2"
        math2_node.operation = 'MULTIPLY'
        math2_node.inputs[1].default_value = 1
        math2_node.location = (190, -610)

        mapping_node = nodes.new(type='ShaderNodeMapping')
        mapping_node.name = "Detail Mapping"
        mapping_node.location = (-1120, 74)

        tc_node = nodes.new(type='ShaderNodeTexCoord')
        tc_node.name = "Detail Texture Coordinate"
        tc_node.location = (-1300, 74)

        detail_mult_node = nodes.new(type='ShaderNodeValue')
        detail_mult_node.name = "Detail Multiplier"
        detail_mult_node.location = (-1310, -196)
        detail_mult_node.outputs[0].default_value = 0.5

        detail_mix_node = nodes.new(type='ShaderNodeMix')
        detail_mix_node.name = "Detail Mix"
        detail_mix_node.data_type = 'RGBA'
        detail_mix_node.blend_type = 'MIX'
        detail_mix_node.clamp_factor = 0
        detail_mix_node.clamp_result = 0
        detail_mix_node.factor_mode = 'NON_UNIFORM'
        detail_mix_node.location = (10, 570)

        alpha_mix_node = nodes.new(type='ShaderNodeMix')
        alpha_mix_node.name = "Blend Alpha Mix"
        alpha_mix_node.data_type = 'FLOAT'
        alpha_mix_node.location = (-175, 570)

        pbr_mapping_node = nodes.new(type='ShaderNodeMapping')
        pbr_mapping_node.name = "PBRMapping"
        pbr_mapping_node.location = (-1120, -300)

        pbr_tc_node = nodes.new(type='ShaderNodeTexCoord')
        pbr_tc_node.name = "PBRTexture Coordinate"
        pbr_tc_node.location = (-1300, -300)

        pbr_mult_node = nodes.new(type='ShaderNodeValue')
        pbr_mult_node.name = "PBRMultiplier"
        pbr_mult_node.location = (-1310, -570)
        pbr_mult_node.outputs[0].default_value = 1

        ksmaterial_node = nodes.new('ShaderNodeGroup')
        ksmaterial_node.node_tree = create_ksmaterial_group()  # Assuming a function to create the custom node group
        ksmaterial_node.name = "ksMaterial Details"
        ksmaterial_node.location = (-1300, 500)

        detail_normal_mix_node = nodes.new(type='ShaderNodeMix')
        detail_normal_mix_node.name = "Detail Normal Mix"
        detail_normal_mix_node.data_type = 'RGBA'
        detail_normal_mix_node.blend_type = 'MIX'
        detail_normal_mix_node.clamp_factor = 0
        detail_normal_mix_node.clamp_result = 0
        detail_normal_mix_node.factor_mode = 'NON_UNIFORM'
        detail_normal_mix_node.location = (300, -130)

        # Create the Principled BSDF and Material Output nodes
        principled_bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled_bsdf_node.name = "Principled BSDF"
        principled_bsdf_node.location = (300, 0)

        mat_output_node = nodes.new(type='ShaderNodeOutputMaterial')
        mat_output_node.name = "Material Output"
        mat_output_node.location = (500, 0)

        # Connect nodes (Example: Connecting Image Texture node to Principled BSDF)
        for i, img_tex_node in enumerate(img_tex_nodes):
            if i == 0:
                links.new(img_tex_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
            # You can add more connections as required here.

        links.new(principled_bsdf_node.outputs[0], mat_output_node.inputs[0])

        # Store node names for later use
        material["ImageTextureNames"] = [node.name for node in img_tex_nodes]

def create_ksmaterial_group():
    # Create the custom node group for ksMaterial_Details
    node_group = bpy.data.node_groups.new(type='ShaderNodeTree', name='ksMaterial_Details')
    input_names = ["Is Base Color", "Is Normal", "Is Texture Map", "Is Detail", "Is PBR", "Is Transparent"]
    for input_name in input_names:
        node_group.inputs.new('NodeSocketBool', input_name)
    node_group.inputs.new('NodeSocketFloat', "Detail Mult")
    node_group.inputs.new('NodeSocketFloat', "PBR Mult")
    return node_group


# Assign textures to nodes
def assign_textures_to_nodes(material, textures):
    img_tex_node_names = material.get("ImageTextureNames", [])
    for i, tex_path in enumerate(textures):
        if i < len(img_tex_node_names):
            img_tex_node_name = img_tex_node_names[i]
            img_tex_node = material.node_tree.nodes.get(img_tex_node_name)

            if img_tex_node and os.path.exists(tex_path):
                image_name = os.path.basename(tex_path)
                if image_name in bpy.data.images:
                    image = bpy.data.images[image_name]
                else:
                    image = bpy.data.images.load(tex_path)
                img_tex_node.image = image
                logging.info(f"Assigned texture {tex_path} to node {img_tex_node_name}")

# Extract and save textures
def extract_and_save_textures(controller, action, rdc_file_path):
    textures = []
    controller.SetFrameEvent(action.eventId, True)
    pipeline_state = controller.GetPipelineState()
    resources = pipeline_state.GetReadOnlyResources(rd.ShaderStage.Fragment)
    reflection = pipeline_state.GetShaderReflection(rd.ShaderStage.Fragment)

    for bind in range(len(resources)):
        if bind >= len(resources) or not resources[bind].resources:
            continue

        texture_id = resources[bind].resources[0].resourceId
        if texture_id == rd.ResourceId.Null():
            continue

        # Extract slot name using reflection
        slot_name = reflection.readOnlyResources[bind].name if bind < len(reflection.readOnlyResources) else None

        # Skip extraction if no slot name or slot is not "tx"
        if not slot_name or not slot_name.startswith("tx") or "txCube" in slot_name:
            continue

        texture_path = save_texture(controller, texture_id, slot_name, rdc_file_path)
        if texture_path:
            textures.append((slot_name, texture_path))

    return textures

# Extract and import mesh
def extract_and_import_mesh(controller, action):
    logging.info(f"Extracting mesh data for action {action.eventId}")
    controller.SetFrameEvent(action.eventId, True)

    try:
        d3d11 = controller.GetD3D11PipelineState()
        ia = d3d11.inputAssembly
        ibuffer = ia.indexBuffer

        if ibuffer.resourceId == rd.ResourceId.Null():
            logging.info(f"No index buffer found for action {action.eventId}. Skipping.")
            return

        index_byte_stride = ibuffer.byteStride
        if index_byte_stride not in [2, 4]:
            logging.warning(f"Unsupported index byte stride {index_byte_stride} for action {action.eventId}. Skipping.")
            return

        vbuffers = ia.vertexBuffers
        vinputs = ia.layouts

        if not vbuffers or not vinputs:
            logging.info(f"No vertex buffers or inputs found for action {action.eventId}.")
            return

        position_elem = None
        uv_elem = None
        for input_elem in vinputs:
            if input_elem.semanticName.lower() == 'position':
                position_elem = input_elem
            elif input_elem.semanticName.lower() == 'texcoord':
                uv_elem = input_elem

        if position_elem is None:
            logging.info(f"No position attribute found for action {action.eventId}.")
            return

        vb_index = position_elem.inputSlot
        if vb_index >= len(vbuffers):
            logging.warning(f"Vertex buffer index out of range for action {action.eventId}.")
            return

        vbuffer = vbuffers[vb_index]
        if vbuffer.resourceId == rd.ResourceId.Null():
            logging.info(f"No vertex buffer found for action {action.eventId}.")
            return

        vertex_byte_stride = vbuffer.byteStride
        estimated_vertex_size = action.numIndices * vertex_byte_stride
        vertex_data = controller.GetBufferData(vbuffer.resourceId, vbuffer.byteOffset, estimated_vertex_size)

        positions = []
        for i in range(0, len(vertex_data), vertex_byte_stride):
            x, y, z = struct.unpack_from('fff', vertex_data, i)
            positions.append((x, y, z))

        uv_data = None
        if uv_elem:
            uv_data = []
            uv_offset = uv_elem.byteOffset
            for i in range(0, len(vertex_data), vertex_byte_stride):
                u, v = struct.unpack_from('ff', vertex_data, i + uv_offset)
                uv_data.append((u, 1 - v))

        index_data = controller.GetBufferData(ibuffer.resourceId, ibuffer.byteOffset, action.numIndices * index_byte_stride)
        indices = []
        for i in range(0, len(index_data), index_byte_stride):
            if index_byte_stride == 2:
                indices.append(struct.unpack_from('H', index_data, i)[0])
            else:
                indices.append(struct.unpack_from('I', index_data, i)[0])

        if len(positions) > MAX_VERTICES or len(indices) > MAX_INDICES:
            logging.warning(f"Skipping mesh {action.eventId} due to size limit.")
            return

        mesh_name = f"Mesh_{action.eventId}"
        create_mesh_in_blender(positions, indices, uv_data, mesh_name)

    except Exception as e:
        logging.error(f"Failed to extract and import mesh for action {action.eventId}: {e}")


def create_mesh_in_blender(positions, indices, uvs, mesh_name):
    if not positions or not indices:
        logging.warning(f"No positions or indices provided for mesh {mesh_name}.")
        return

    # Create the RDC collection if it doesn't already exist
    rdc_collection_name = "RDC"
    if rdc_collection_name not in bpy.data.collections:
        rdc_collection = bpy.data.collections.new(rdc_collection_name)
        bpy.context.scene.collection.children.link(rdc_collection)
    else:
        rdc_collection = bpy.data.collections[rdc_collection_name]

    # Create a new mesh and object
    mesh = bpy.data.meshes.new(mesh_name)
    obj = bpy.data.objects.new(mesh_name, mesh)
    
    # Link the object to the RDC collection
    rdc_collection.objects.link(obj)

    # Log the vertices and faces count
    logging.info(f"Number of vertices: {len(positions)}")
    logging.info(f"Number of faces: {len(indices) // 3}")

    # Check that the indices are properly divisible by 3 for triangle faces
    if len(indices) % 3 != 0:
        logging.error(f"Indices count is not a multiple of 3. The mesh may not form proper triangles.")
        return

    # Construct faces as a list of tuples
    faces = [indices[i:i+3] for i in range(0, len(indices), 3)]

    # Log a sample of faces to debug the structure
    logging.info(f"Sample faces: {faces[:5]}")

    # Create the mesh using the vertices and faces
    mesh.from_pydata(positions, [], faces)

    if uvs:
        uv_layer = mesh.uv_layers.new(name="UVMap")
        mesh.uv_layers.active = uv_layer
        uv_data = uv_layer.data
        for loop in mesh.loops:
            uv_data[loop.index].uv = uvs[loop.vertex_index]

    # Update the mesh
    mesh.update()

    # Shade the mesh smooth
    for face in mesh.polygons:
        face.use_smooth = True

    # Enable Auto Smooth with a 30-degree angle
    mesh.use_auto_smooth = True
    mesh.auto_smooth_angle = 0.698132  # 30 degrees in radians

    logging.info(f"Mesh {mesh_name} created in Blender with UVs and auto smooth enabled.")



# Process action
def process_action(controller, action, min_action_id, max_action_id, rdc_file_path):
    if max_action_id != -1 and (action.eventId < min_action_id or action.eventId > max_action_id):
        return

    textures = extract_and_save_textures(controller, action, rdc_file_path)
    material = create_or_get_material(action.eventId)
    assign_textures_to_nodes(material, textures)
    extract_and_import_mesh(controller, action)

    mesh_name = f"Mesh_{action.eventId}"
    obj = bpy.data.objects.get(mesh_name)
    if obj:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)

# Import meshes from RDC
def import_meshes_from_rdc(rdc_file_path, min_action_id, max_action_id):
    setup_logging(rdc_file_path)
    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(rdc_file_path, '', None)
    if status != rd.ReplayStatus.Succeeded:
        raise RuntimeError(f'Failed to open capture: {status}')

    options = rd.ReplayOptions()
    status, controller = cap.OpenCapture(options, None)
    if status != rd.ReplayStatus.Succeeded:
        raise RuntimeError(f'Failed to initialize replay: {status}')

    actions = controller.GetRootActions()
    for action in actions:
        process_action(controller, action, min_action_id, max_action_id, rdc_file_path)

    controller.Shutdown()
    cap.Shutdown()
    logging.info("Import completed and controller shut down.")
