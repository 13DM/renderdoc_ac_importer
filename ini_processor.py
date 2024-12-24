import bpy
from bpy.types import Operator  # Import Operator for creating custom Blender operators
from bpy_extras.io_utils import ImportHelper  # Import ImportHelper for file selection dialog
import shutil
import os

# The operator for reading the ini persistence files and applying to the NR model
class OBJECT_OT_acet_read_ini(Operator, ImportHelper):
    bl_idname = "acet.read_ini"
    bl_label = "Read INI"
    bl_description = "This will open a dialog to select an ini file from a converted kn5. It wil then apply the correct shader values based off the material details in the ini"
    
    filename_ext = ".ini"

    def execute(self, context):
        # Get the filepath from the operator
        ini_filepath = self.filepath
        # Process the selected INI file
        main_ini_processer(ini_filepath)
        self.report({'INFO'}, 'ACET: INI file processed')
        return {'FINISHED'}
                            
def custom_ini_parser(filepath):
    material_data = {}
    current_section = None
    
    with open(filepath, 'r') as file:
        for line in file:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]  # Extract section name
                material_data[current_section] = {'textures': {}, 'vars': {}}
            elif '=' in line and current_section:
                key, value = line.split('=', 1)
                if key == 'NAME':
                    material_data[current_section]['name'] = value
                elif key.startswith('VAR_') and key.endswith('_NAME'):
                    var_index = key.split('_')[1]
                    material_data[current_section]['vars'][var_index] = {'name': value}
                elif key.startswith('VAR_') and key.endswith('_FLOAT1'):
                    var_index = key.split('_')[1]
                    material_data[current_section]['vars'][var_index]['float1'] = value
                elif key.startswith('RES_') and key.endswith('_TEXTURE'):
                    res_index = key.split('_')[1]
                    material_data[current_section]['textures'][res_index] = value
                else:
                    material_data[current_section][key] = value

    return material_data


# function to verify image nodes actually have an image. If not, then ya know add it. 

def apply_image_to_node(node, filepath):
    """
    Apply an image to a Blender node if it does not already have one.

    Args:
    node (bpy.types.Node): The node to check and apply the image to.
    filepath (str): The full path to the image file.
    """
    # Check if the node has an image already
    if not hasattr(node, 'image') or node.image is None:
        # Extract the image name from the filepath
        image_name = os.path.basename(filepath)
        
        # Check if the image already exists in Blender's data blocks
        existing_image = bpy.data.images.get(image_name)
        if existing_image:
            # Check the dimensions of the existing image
            #if existing_image.size[0] < 2 or existing_image.size[1] < 2:
                #print(f"Image {image_name} is too small: {existing_image.size[0]}x{existing_image.size[1]}")
            node.image = existing_image
            return True
        else:
            # Check if the provided filepath is a valid image file
            if os.path.isfile(filepath) and filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.dds')):
                try:
                    # Load the image from the filepath
                    image = bpy.data.images.load(filepath)
                    # Check the dimensions of the loaded image
                    #if image.size[0] < 2 or image.size[1] < 2:
                        #print(f"Loaded image {image_name} is too small: {image.size[0]}x{image.size[1]}")
                    # Apply the image to the node
                    node.image = image
                    return True
                except Exception as e:
                    print(f"Failed to load image: {e}")
                    return False
            else:
                print(f"Invalid image file path: {filepath}")
                return False
    else:
        #print(f"Node already has an image: {node.image.name}")
        return False

# A quick function to check if the texture is encrypted still and needs to be replaced. 

def is_texture_encrypted(node):
    """
    Check if the image associated with the specified node is smaller than 2x2 pixels.

    Args:
    node (bpy.types.Node): The node to check the image size for.

    Returns:
    bool: True if the image is smaller than 2x2 pixels, False otherwise.
    """
    if hasattr(node, 'image') and node.image is not None:
        image = node.image
        # Check the dimensions of the image
        if image.size[0] < 2 or image.size[1] < 2:
            print(f"Image {image.name} is too small: {image.size[0]}x{image.size[1]}")
            return True
        else:
            return False
    else:
        print("Node does not have an image.")
        return False


def apply_material_settings_from_ini(material_data, filepath):
    # Similar implementation as before, but using the custom parsed data
    print(f"{material_data} \n\n")
    
    directory, filename = os.path.split(filepath)
    texture_directory = os.path.join(directory, "texture")
    
    tex_names = []
    
    encrypted_textures = []
    
    ini_error_text = f'----------------------------------------\n'
    ini_error_text += f'Report of materials with issues during application of ini: \n\n'

    for key, value in material_data.items():
        if key.startswith('MATERIAL_'):
            print(f"Material: {value.get('name')}")
            print(f"--Material Shader: {value.get('SHADER')}")
            print(f"--Material Texture Count: {value.get('RESCOUNT')}")
            
            # Set Variables for shader things
            _currentMatName = str(value.get('name'))
            _currentMat = None
            _currentDetailMult = None
            _currentDetailNMMult = None
            _useDetail = False
            _currentDetailNormalBlend = None
            
            if tex_names is not None:
                tex_names.clear()
            
            # Get the material we are working with through the ini file and see if it exists in the file
            if bpy.data.materials.get(_currentMatName):
                _currentMat = bpy.data.materials.get(_currentMatName)
            else:
                _currentMat = None
                
            # If material is not found, skip this iteration
            if _currentMat is None:
                continue
            
            # Add in additional logic to check the material being used.
            material_used = any(obj for obj in bpy.data.objects if hasattr(obj.data, 'materials') and _currentMatName in [mat.name for mat in obj.data.materials])
            if not material_used:
                print(f"Material '{_currentMatName}' not used on any mesh object. Skipping.")
                print(f"")
                ini_error_text += f"Material '{_currentMatName}' not used on any mesh object. It was skipped. \n"
                continue
            
            _currentShader = value.get('SHADER')
            # Fix Alpha Blend Value as boolean
            _currentAlphaBlend = False
            if int(value.get('ALPHABLEND')) > 0:
                _currentAlphaBlend = True
            else:
                _currentAlphaBlend = False
                
            #print(f"--Material Alpha Blend: {_currentAlphaBlend}")
            # Fix Alpha Test Value as boolean
            _currentAlphaTest = False
            if value.get('APLHATEST') == None:
                if int(value.get('ALPHATEST')) > 0:
                    _currentAlphaTest = True
                else:
                    _currentAlphaTest = False
            else:
                if int(value.get('APLHATEST')) > 0:
                    _currentAlphaTest = True
                else:
                    _currentAlphaTest = False
            
            #print(f"--Material Alpha Test: {_currentAlphaTest}")
            
            # Get the total number of images for the material
            _currentTextureCount = value.get('RESCOUNT')
            
            vars = value.get('vars')
            vv1_prev = None  # Initialize vv1_prev here
            if vars:
                for var_key, var_value in vars.items():
                    for var_key1, var_value1 in var_value.items():
                        if vv1_prev is None:
                            # Store the ambient value for the next iteration
                            vv1_prev = var_value.get('name')
                        else:
                            if vv1_prev is not None:
                                if vv1_prev == "normalUVMultiplier":
                                    _currentDetailNMMult = float(var_value1)
                                if vv1_prev == "detailUVMultiplier":
                                    _currentDetailMult = float(var_value1)
                                if vv1_prev == "useDetail":
                                    if float(var_value1) > 0:
                                        _useDetail = True
                                if vv1_prev == "detailNormalBlend":
                                    _currentDetailNormalBlend = float(var_value1)
                                
                                # Print the ambient value from the previous iteration
                                #print(f"----{vv1_prev}: {var_value1}")
                                vv1_prev = None  # Reset ambient_value
                            #print(f"----Vars {var_key1}: {var_value1}")
            textures = value.get('textures')
            if textures:
                slot = 0
                for tex_key, tex_value in textures.items():
                    #if slot > 0:
                        #print(f"----Texture Image.00{slot}: {tex_value}")
                    #else:
                        #print(f"----Texture Image: {tex_value}")
                    tex_names.append(tex_value)
                    print(f"Tex name = {tex_names[slot]}")
                    slot += 1
                    
            #print(f"")
            
            
            
            #print(f"Use Detail: {_useDetail}")
            #print(f"Detail Multiplier: {_currentDetailMult}")
            #print(f"Normal Multiplier: {_currentDetailNMMult}")
            #print(f"Normal Blend: {_currentDetailNormalBlend}")
            
            # Gather nodes for applying shader values to
            normal_map_node = None
            separate_color_node = None
            math1_node = None
            math2_node = None
            mapping_node = None
            tc_node = None
            detail_mult_node = None
            detail_mix_node = None
            alpha_mix_node = None
            pbr_mapping_node = None
            pbr_tc_node = None
            pbr_mult_node = None
            ksmaterial_node = None
            detail_normal_mix_node = None
            principled_bsdf_node = None
            img_tex_node = None
            img_tex_1_node = None
            img_tex_2_node = None
            img_tex_3_node = None
            img_tex_4_node = None
            img_tex_5_node = None
            img_tex_6_node = None
            img_tex_7_node = None
            img_tex_8_node = None
            img_tex_9_node = None
            img_tex_10_node = None
            
            nodes = _currentMat.node_tree.nodes
            links = _currentMat.node_tree.links
            
            #print(f"Total Nodes in Material {len(nodes) - 1}")
            
            # If nodes exist set them appropriately
            for node in nodes:
                if node.name == "Normal Map 1":
                    normal_map_node = node  
                    #print(f"Normal: {node}")
                if node.name == "TxtMap Separate Color":
                    separate_color_node = node
                    #print(f"Sep Color: {node}")
                if node.name == "TxtMap Math 1":
                    math1_node = node
                    #print(f"math1: {node}")
                if node.name == "TxtMap Math 2":
                    math2_node = node
                    #print(f"Math2: {node}")
                if node.name == "Detail Mapping":
                    mapping_node = node
                    #print(f"Detail Mapping: {node}")
                if node.name == "Detail Texture Coordinate":
                    tc_node = node
                    #print(f"TC: {node}")
                if node.name == "Detail Multiplier":
                    detail_mult_node = node
                    #print(f"Detail Mult: {node}")
                if node.name == "Detail Mix":
                    detail_mix_node = node
                    #print(f"Detail Mix: {node}")
                if node.name == "Blend Alpha Mix":
                    alpha_mix_node = node
                    #print(f"Alpha Mix: {node}")
                if node.name == "PBRMapping":
                    pbr_mapping_node = node
                    #print(f"PBR Map: {node}")
                if node.name == "PBRTexture Coordinate":
                    pbr_tc_node = node
                    #print(f"PBR TC: {node}")
                if node.name == "PBRMultiplier":
                    pbr_mult_node = node
                    #print(f"PBR Mult: {node}")
                if node.name == "ksMaterial Details":
                    ksmaterial_node = node
                    #print(f"ksMat: {node}")
                if node.name == "Detail Normal Mix":
                    detail_normal_mix_node = node
                    #print(f"Detail Normal Mix: {node}")
                if node.name == "Principled BSDF":
                    principled_bsdf_node = node
                    #print(f"PBSDF: {node}")
                if node.name == "Image Texture":
                    img_tex_1_node = node
                    #print(f"Image Texture: {node}")
                if node.name == "Image Texture.001":
                    img_tex_2_node = node
                    #print(f"Image Texture.001: {node}")
                if node.name == "Image Texture.002":
                    img_tex_3_node = node
                    #print(f"Image Texture.002: {node}")
                if node.name == "Image Texture.003":
                    img_tex_4_node = node
                    #print(f"Image Texture.003: {node}")
                if node.name == "Image Texture.004":
                    img_tex_5_node = node
                    #print(f"Image Texture.004: {node}")
                if node.name == "Image Texture.005":
                    img_tex_6_node = node
                    #print(f"Image Texture.005: {node}")
                if node.name == "Image Texture.006":
                    img_tex_7_node = node
                    #print(f"Image Texture.006: {node}")
                if node.name == "Image Texture.007":
                    img_tex_8_node = node
                    #print(f"Image Texture.007: {node}")
                if node.name == "Image Texture.008":
                    img_tex_9_node = node
                    #print(f"Image Texture.008: {node}")
                if node.name == "Image Texture.009":
                    img_tex_10_node = node
                    
            # Additionally add in logic for try catch
            # This is so that if there is an issue processing a material, it will continue working on it. 
            # This is to avoid issue when working with bad models or materials from rips and mods
            
            try:
                
                #apply the shader socket connections
                if _currentAlphaBlend == True:
                    _currentMat.blend_method = "BLEND"
                    _currentMat.show_transparent_back = 0
                    if _useDetail == True:
                        links.new(alpha_mix_node.outputs[0], principled_bsdf_node.inputs['Alpha'])
                    else:
                        links.new(img_tex_1_node.outputs['Alpha'], principled_bsdf_node.inputs['Alpha'])
                if _currentAlphaTest == True:
                    _currentMat.blend_method = "HASHED"
                    _currentMat.show_transparent_back = 0
                    if _useDetail == True:
                        links.new(alpha_mix_node.outputs[0], principled_bsdf_node.inputs['Alpha'])
                    else:
                        links.new(img_tex_1_node.outputs['Alpha'], principled_bsdf_node.inputs['Alpha'])
                
                if int(_currentTextureCount) == 1:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    links.new(img_tex_1_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
                    
                    rename_images(img_tex_1_node, tex_names[0])
                    
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])

                if int(_currentTextureCount) == 2:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))

                    if _currentShader not in ("ksGrass", "ksPostFOG_MS"):
                        links.new(img_tex_1_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
                        
                        links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                        links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                        
                        img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                    
                        rename_images(img_tex_1_node, tex_names[0])
                        rename_images(img_tex_2_node, tex_names[1])
                    if _currentShader != "ksPerPixelNM_UVMult":
                        print(f"WARN: Shader type: {_currentShader} utilizes multipliers which are not configured for the base color or normal texture.")
                        
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])

                    
                if int(_currentTextureCount) == 3:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))
                    apply_image_to_node(img_tex_3_node, os.path.join(texture_directory, tex_names[2]))

                    if _currentShader == "ksPerPixelAT_NM_emissive":
                        links.new(img_tex_1_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
                        
                        links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                        links.new(img_tex_2_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                        
                        img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                        
                        links.new(img_tex_3_node.outputs['Color'], principled_bsdf_node.inputs['Emission'])
                    
                        rename_images(img_tex_1_node, tex_names[0])
                        rename_images(img_tex_2_node, tex_names[1])
                        rename_images(img_tex_3_node, tex_names[2])
                    if _currentShader == "ksPerPixel_dual_layer":
                        links.new(img_tex_1_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
                    
                        rename_images(img_tex_1_node, tex_names[0])
                        rename_images(img_tex_2_node, tex_names[1])
                        rename_images(img_tex_3_node, tex_names[2])
                        print(f"WARN: Shader type: {_currentShader} utilizes layers and mask which are not configured for the shader. Mapping original color only.")
                    if _currentShader == "ksPerPixelAT_NM_emissive":
                        links.new(img_tex_1_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
                        
                        links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                        links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                        
                        img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                    
                        rename_images(img_tex_1_node, tex_names[0])
                        rename_images(img_tex_2_node, tex_names[1])
                        rename_images(img_tex_3_node, tex_names[2])
                        
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])
                    if is_texture_encrypted(img_tex_3_node) and tex_names[2] not in encrypted_textures:
                        ini_error_text += f'{tex_names[2]} is encrypted. \n'
                        encrypted_textures.append(tex_names[2])

                        
                        print(f"WARN: Shader type: {_currentShader} utilizes multipliers which are not configured for the base color or normal texture.")
                if int(_currentTextureCount) == 4:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))
                    apply_image_to_node(img_tex_3_node, os.path.join(texture_directory, tex_names[2]))
                    apply_image_to_node(img_tex_4_node, os.path.join(texture_directory, tex_names[3]))

                    # IsDetail true map the base colors to the mix nodes
                    if _useDetail == True:
                        # Base Color
                        links.new(img_tex_1_node.outputs['Color'], detail_mix_node.inputs[6])
                        links.new(img_tex_1_node.outputs['Alpha'], alpha_mix_node.inputs[2])
                        
                        links.new(img_tex_4_node.outputs['Color'], detail_mix_node.inputs[7])
                        links.new(img_tex_4_node.outputs['Alpha'], alpha_mix_node.inputs[3])
                        
                        alpha_mix_node.inputs[0].default_value = 0.95
                        
                        links.new(alpha_mix_node.outputs[0], detail_mix_node.inputs[0])
                        links.new(detail_mix_node.outputs[2], principled_bsdf_node.inputs['Base Color'])
                        
                        # Normal
                        links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                        links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                        
                        img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                        
                        # Texture Map
                        links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                        
                        links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                        links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                        links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                        
                        links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                        links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                        
                        img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                        
                        # Detail 
                        links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                        links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                        links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                        
                        if _currentDetailMult is None:
                            detail_mult_node.outputs[0].default_value = 1.0
                        else:
                            detail_mult_node.outputs[0].default_value = float(_currentDetailMult)
                    else:
                        # Base Color
                        links.new(img_tex_1_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
                        
                        # Normal
                        links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                        links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                        
                        img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                        
                        # Texture Map
                        links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                        
                        links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                        links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                        links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                        
                        links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                        links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                        
                        img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                        
                        # Detail 
                        links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                        links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                        links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                        
                        if _currentDetailMult is None:
                            detail_mult_node.outputs[0].default_value = 1.0
                        else:
                            detail_mult_node.outputs[0].default_value = float(_currentDetailMult)
                    
                    rename_images(img_tex_1_node, tex_names[0])
                    rename_images(img_tex_2_node, tex_names[1])
                    rename_images(img_tex_3_node, tex_names[2])
                    rename_images(img_tex_4_node, tex_names[3])
                    
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])
                    if is_texture_encrypted(img_tex_3_node) and tex_names[2] not in encrypted_textures:
                        ini_error_text += f'{tex_names[2]} is encrypted. \n'
                        encrypted_textures.append(tex_names[2])
                    if is_texture_encrypted(img_tex_4_node) and tex_names[3] not in encrypted_textures:
                        ini_error_text += f'{tex_names[3]} is encrypted. \n'
                        encrypted_textures.append(tex_names[3])

                    
                if int(_currentTextureCount) == 5:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))
                    apply_image_to_node(img_tex_3_node, os.path.join(texture_directory, tex_names[2]))
                    apply_image_to_node(img_tex_4_node, os.path.join(texture_directory, tex_names[3]))
                    apply_image_to_node(img_tex_5_node, os.path.join(texture_directory, tex_names[4]))
                    
                    # IsDetail true map the base colors to the mix nodes
                    if _useDetail == True:
                        if _currentShader in ("ksDiscBrake", "ksTyres"):
                            links.new(img_tex_1_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
                        
                            links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                            links.new(img_tex_2_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                        
                            img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                        elif _currentShader == "ksPerPixelMultiMap_emissive":
                            # Base Color
                            links.new(img_tex_1_node.outputs['Color'], detail_mix_node.inputs[6])
                            links.new(img_tex_1_node.outputs['Alpha'], alpha_mix_node.inputs[2])
                            
                            links.new(img_tex_4_node.outputs['Color'], detail_mix_node.inputs[7])
                            links.new(img_tex_4_node.outputs['Alpha'], alpha_mix_node.inputs[3])
                            
                            alpha_mix_node.inputs[0].default_value = 0.95
                            
                            links.new(alpha_mix_node.outputs[0], detail_mix_node.inputs[0])
                            links.new(detail_mix_node.outputs[2], principled_bsdf_node.inputs['Base Color'])
                            
                            # Normal
                            links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                            links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                            
                            img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Texture Map
                            links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                            
                            links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                            links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                            links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                            
                            links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                            links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                            
                            img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Detail 
                            links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                            links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                            links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                            
                            detail_mult_node.outputs[0].default_value = float(_currentDetailMult)   
                            
                            # Emission
                            links.new(img_tex_5_node.outputs['Color'], principled_bsdf_node.inputs['Emission'])
                            
                        elif _currentShader == "ksPerPixelMultiMap_AT_emissive":
                            # Base Color
                            links.new(img_tex_1_node.outputs['Color'], detail_mix_node.inputs[6])
                            links.new(img_tex_1_node.outputs['Alpha'], alpha_mix_node.inputs[2])
                            
                            links.new(img_tex_4_node.outputs['Color'], detail_mix_node.inputs[7])
                            links.new(img_tex_4_node.outputs['Alpha'], alpha_mix_node.inputs[3])
                            
                            alpha_mix_node.inputs[0].default_value = 0.95
                            
                            links.new(alpha_mix_node.outputs[0], detail_mix_node.inputs[0])
                            links.new(detail_mix_node.outputs[2], principled_bsdf_node.inputs['Base Color'])
                            
                            # Normal
                            links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                            links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                            
                            img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Texture Map
                            links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                            
                            links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                            links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                            links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                            
                            links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                            links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                            
                            img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Detail 
                            links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                            links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                            links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                            
                            # Emission
                            links.new(img_tex_5_node.outputs['Color'], principled_bsdf_node.inputs['Emission'])
                            
                            detail_mult_node.outputs[0].default_value = float(_currentDetailMult)    
                            
                        elif _currentShader in ("ksPerPixelMultiMap_NMDetail", "ksSkinnedMesh_NMDetaill"):
                            # Base Color
                            links.new(img_tex_1_node.outputs['Color'], detail_mix_node.inputs[6])
                            links.new(img_tex_1_node.outputs['Alpha'], alpha_mix_node.inputs[2])
                            
                            links.new(img_tex_4_node.outputs['Color'], detail_mix_node.inputs[7])
                            links.new(img_tex_4_node.outputs['Alpha'], alpha_mix_node.inputs[3])
                            
                            alpha_mix_node.inputs[0].default_value = 0.95
                            
                            links.new(alpha_mix_node.outputs[0], detail_mix_node.inputs[0])
                            links.new(detail_mix_node.outputs[2], principled_bsdf_node.inputs['Base Color'])
                            
                            # Normal
                            links.new(img_tex_2_node.outputs['Color'], detail_normal_mix_node.inputs[6])
                            links.new(img_tex_5_node.outputs['Color'], detail_normal_mix_node.inputs[7])
                            
                            links.new(detail_normal_mix_node.outputs[2], normal_map_node.inputs['Color'])
                            
                            links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                            
                            img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                            img_tex_5_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Texture Map
                            links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                            
                            links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                            links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                            links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                            
                            links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                            links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                            
                            img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Detail 
                            links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                            links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                            links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                            
                            if _currentDetailMult is None:
                                detail_mult_node.outputs[0].default_value = 1.0
                            else:
                                detail_mult_node.outputs[0].default_value = float(_currentDetailMult)
                            
                            links.new(pbr_mapping_node.outputs['Vector'], img_tex_5_node.inputs['Vector'])
                            links.new(pbr_tc_node.outputs['UV'], pbr_mapping_node.inputs['Vector'])
                            links.new(pbr_mult_node.outputs['Value'], pbr_mapping_node.inputs['Scale'])
                            
                            detail_normal_mix_node.inputs[0].default_value = float(_currentDetailNormalBlend)
                            
                            pbr_mult_node.outputs[0].default_value = float(_currentDetailMult)
                            
                            
                        elif _currentShader == "smSticker":
                            # Base Color
                            links.new(img_tex_1_node.outputs['Color'], detail_mix_node.inputs[6])
                            links.new(img_tex_1_node.outputs['Alpha'], alpha_mix_node.inputs[2])
                            
                            links.new(img_tex_4_node.outputs['Color'], detail_mix_node.inputs[7])
                            links.new(img_tex_4_node.outputs['Alpha'], alpha_mix_node.inputs[3])
                            
                            alpha_mix_node.inputs[0].default_value = 0.95
                            
                            links.new(alpha_mix_node.outputs[0], detail_mix_node.inputs[0])
                            links.new(detail_mix_node.outputs[2], principled_bsdf_node.inputs['Base Color'])
                            
                            # Normal
                            links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                            
                            links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                            
                            img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Texture Map
                            links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                            
                            links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                            links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                            links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                            
                            links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                            links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                            
                            img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Detail 
                            links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                            links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                            links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                            
                            if _currentDetailMult is None:
                                detail_mult_node.outputs[0].default_value = 1.0
                            else:
                                detail_mult_node.outputs[0].default_value = float(_currentDetailMult)
                            
                            links.new(pbr_mapping_node.outputs['Vector'], img_tex_2_node.inputs['Vector'])
                            links.new(pbr_tc_node.outputs['UV'], pbr_mapping_node.inputs['Vector'])
                            links.new(pbr_mult_node.outputs['Value'], pbr_mapping_node.inputs['Scale'])
                            
                            pbr_mult_node.outputs[0].default_value = float(_currentDetailNMMult)
                            
                            
                        elif _currentShader == "ksPerPixelMultiMap_AT_NMDetail":
                            # Base Color
                            links.new(img_tex_1_node.outputs['Color'], detail_mix_node.inputs[6])
                            links.new(img_tex_1_node.outputs['Alpha'], alpha_mix_node.inputs[2])
                            
                            links.new(img_tex_4_node.outputs['Color'], detail_mix_node.inputs[7])
                            links.new(img_tex_4_node.outputs['Alpha'], alpha_mix_node.inputs[3])
                            
                            alpha_mix_node.inputs[0].default_value = 0.95
                            
                            links.new(alpha_mix_node.outputs[0], detail_mix_node.inputs[0])
                            links.new(detail_mix_node.outputs[2], principled_bsdf_node.inputs['Base Color'])
                            
                            # Normal
                            links.new(img_tex_2_node.outputs['Color'], detail_normal_mix_node.inputs[6])
                            links.new(img_tex_5_node.outputs['Color'], detail_normal_mix_node.inputs[7])
                            
                            links.new(detail_normal_mix_node.outputs[2], normal_map_node.inputs['Color'])
                            
                            links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                            
                            # Additional try catch to avoid errors when applying 
                            try:
                                img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                            except AttributeError as e:
                                print(f"Unable to apply color_space setting to Normal Image on material '{_currentMatName}': {str(e)}")
                            try:
                                img_tex_5_node.image.colorspace_settings.name = 'Non-Color'
                            except AttributeError as e:
                                print(f"Unable to apply color_space setting to Detail Normal Image on material '{_currentMatName}': {str(e)}")
                            
                            # Texture Map
                            links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                            
                            links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                            links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                            links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                            
                            links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                            links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                            
                            img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Detail 
                            links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                            links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                            links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                            
                            if _currentDetailMult is None:
                                detail_mult_node.outputs[0].default_value = 1.0
                            else:
                                detail_mult_node.outputs[0].default_value = float(_currentDetailMult)
                            
                            links.new(pbr_mapping_node.outputs['Vector'], img_tex_5_node.inputs['Vector'])
                            links.new(pbr_tc_node.outputs['UV'], pbr_mapping_node.inputs['Vector'])
                            links.new(pbr_mult_node.outputs['Value'], pbr_mapping_node.inputs['Scale'])
                            
                            detail_normal_mix_node.inputs[0].default_value = float(_currentDetailNormalBlend)
                            
                            pbr_mult_node.outputs[0].default_value = float(_currentDetailNMMult)
                            
                            
                        elif _currentShader == "ksPerPixelMultiMap_damage":
                            # Base Color
                            links.new(img_tex_1_node.outputs['Color'], detail_mix_node.inputs[6])
                            links.new(img_tex_1_node.outputs['Alpha'], alpha_mix_node.inputs[2])
                            
                            links.new(img_tex_4_node.outputs['Color'], detail_mix_node.inputs[7])
                            links.new(img_tex_4_node.outputs['Alpha'], alpha_mix_node.inputs[3])
                            
                            alpha_mix_node.inputs[0].default_value = 0.95
                            
                            links.new(alpha_mix_node.outputs[0], detail_mix_node.inputs[0])
                            links.new(detail_mix_node.outputs[2], principled_bsdf_node.inputs['Base Color'])
                            
                            # Normal
                            links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                            links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                            
                            img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Texture Map
                            links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                            
                            links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                            links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                            links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                            
                            links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                            links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                            
                            img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                            
                            # Detail 
                            links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                            links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                            links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                            
                            if _currentDetailMult is None:
                                detail_mult_node.outputs[0].default_value = 1.0
                            else:
                                detail_mult_node.outputs[0].default_value = float(_currentDetailMult)
                    else:
                        # Base Color
                        links.new(img_tex_1_node.outputs['Color'], principled_bsdf_node.inputs['Base Color'])
                        
                        # Normal
                        links.new(img_tex_2_node.outputs['Color'], normal_map_node.inputs['Color'])
                        links.new(normal_map_node.outputs['Normal'], principled_bsdf_node.inputs['Normal'])
                        
                        img_tex_2_node.image.colorspace_settings.name = 'Non-Color'
                        
                        # Texture Map
                        links.new(img_tex_3_node.outputs['Color'], separate_color_node.inputs['Color'])
                        
                        links.new(separate_color_node.outputs[0], principled_bsdf_node.inputs['Specular'])
                        links.new(math1_node.outputs[0], principled_bsdf_node.inputs['Roughness'])
                        links.new(math2_node.outputs[0], principled_bsdf_node.inputs['Metallic'])
                        
                        links.new(separate_color_node.outputs[1], math1_node.inputs[0])
                        links.new(separate_color_node.outputs[2], math2_node.inputs[0])
                        
                        img_tex_3_node.image.colorspace_settings.name = 'Non-Color'
                        
                        # Detail 
                        links.new(mapping_node.outputs['Vector'], img_tex_4_node.inputs['Vector'])
                        links.new(tc_node.outputs['UV'], mapping_node.inputs['Vector'])
                        links.new(detail_mult_node.outputs['Value'], mapping_node.inputs['Scale'])
                        
                        if _currentDetailMult is None:
                            detail_mult_node.outputs[0].default_value = 1.0
                        else:
                            detail_mult_node.outputs[0].default_value = float(_currentDetailMult)
                    
                    rename_images(img_tex_1_node, tex_names[0])
                    rename_images(img_tex_2_node, tex_names[1])
                    rename_images(img_tex_3_node, tex_names[2])
                    rename_images(img_tex_4_node, tex_names[3])
                    rename_images(img_tex_5_node, tex_names[4])
                    
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])
                    if is_texture_encrypted(img_tex_3_node) and tex_names[2] not in encrypted_textures:
                        ini_error_text += f'{tex_names[2]} is encrypted. \n'
                        encrypted_textures.append(tex_names[2])
                    if is_texture_encrypted(img_tex_4_node) and tex_names[3] not in encrypted_textures:
                        ini_error_text += f'{tex_names[3]} is encrypted. \n'
                        encrypted_textures.append(tex_names[3])
                    if is_texture_encrypted(img_tex_5_node) and tex_names[4] not in encrypted_textures:
                        ini_error_text += f'{tex_names[4]} is encrypted. \n'
                        encrypted_textures.append(tex_names[4])
                    
                #if int(_currentTextureCount) > 5:
                if int(_currentTextureCount) == 6:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))
                    apply_image_to_node(img_tex_3_node, os.path.join(texture_directory, tex_names[2]))
                    apply_image_to_node(img_tex_4_node, os.path.join(texture_directory, tex_names[3]))
                    apply_image_to_node(img_tex_5_node, os.path.join(texture_directory, tex_names[4]))
                    apply_image_to_node(img_tex_6_node, os.path.join(texture_directory, tex_names[5]))
                    print(f"Currently unsupported amount of textures. Renaming of files will still occur but no shader details will be setup.")
                    
                    rename_images(img_tex_1_node, tex_names[0])
                    rename_images(img_tex_2_node, tex_names[1])
                    rename_images(img_tex_3_node, tex_names[2])
                    rename_images(img_tex_4_node, tex_names[3])
                    rename_images(img_tex_5_node, tex_names[4])
                    rename_images(img_tex_6_node, tex_names[5])
                    
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])
                    if is_texture_encrypted(img_tex_3_node) and tex_names[2] not in encrypted_textures:
                        ini_error_text += f'{tex_names[2]} is encrypted. \n'
                        encrypted_textures.append(tex_names[2])
                    if is_texture_encrypted(img_tex_4_node) and tex_names[3] not in encrypted_textures:
                        ini_error_text += f'{tex_names[3]} is encrypted. \n'
                        encrypted_textures.append(tex_names[3])
                    if is_texture_encrypted(img_tex_5_node) and tex_names[4] not in encrypted_textures:
                        ini_error_text += f'{tex_names[4]} is encrypted. \n'
                        encrypted_textures.append(tex_names[4])
                    if is_texture_encrypted(img_tex_6_node) and tex_names[5] not in encrypted_textures:
                        ini_error_text += f'{tex_names[5]} is encrypted. \n'
                        encrypted_textures.append(tex_names[5])
                    
                if int(_currentTextureCount) == 7:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))
                    apply_image_to_node(img_tex_3_node, os.path.join(texture_directory, tex_names[2]))
                    apply_image_to_node(img_tex_4_node, os.path.join(texture_directory, tex_names[3]))
                    apply_image_to_node(img_tex_5_node, os.path.join(texture_directory, tex_names[4]))
                    apply_image_to_node(img_tex_6_node, os.path.join(texture_directory, tex_names[5]))
                    apply_image_to_node(img_tex_7_node, os.path.join(texture_directory, tex_names[6]))
                    print(f"Currently unsupported amount of textures. Renaming of files will still occur but no shader details will be setup.")
                    
                    rename_images(img_tex_1_node, tex_names[0])
                    rename_images(img_tex_2_node, tex_names[1])
                    rename_images(img_tex_3_node, tex_names[2])
                    rename_images(img_tex_4_node, tex_names[3])
                    rename_images(img_tex_5_node, tex_names[4])
                    rename_images(img_tex_6_node, tex_names[5])
                    rename_images(img_tex_7_node, tex_names[6])
                    
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])
                    if is_texture_encrypted(img_tex_3_node) and tex_names[2] not in encrypted_textures:
                        ini_error_text += f'{tex_names[2]} is encrypted. \n'
                        encrypted_textures.append(tex_names[2])
                    if is_texture_encrypted(img_tex_4_node) and tex_names[3] not in encrypted_textures:
                        ini_error_text += f'{tex_names[3]} is encrypted. \n'
                        encrypted_textures.append(tex_names[3])
                    if is_texture_encrypted(img_tex_5_node) and tex_names[4] not in encrypted_textures:
                        ini_error_text += f'{tex_names[4]} is encrypted. \n'
                        encrypted_textures.append(tex_names[4])
                    if is_texture_encrypted(img_tex_6_node) and tex_names[5] not in encrypted_textures:
                        ini_error_text += f'{tex_names[5]} is encrypted. \n'
                        encrypted_textures.append(tex_names[5])
                    if is_texture_encrypted(img_tex_7_node) and tex_names[6] not in encrypted_textures:
                        ini_error_text += f'{tex_names[6]} is encrypted. \n'
                        encrypted_textures.append(tex_names[6])

                    
                if int(_currentTextureCount) == 8:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))
                    apply_image_to_node(img_tex_3_node, os.path.join(texture_directory, tex_names[2]))
                    apply_image_to_node(img_tex_4_node, os.path.join(texture_directory, tex_names[3]))
                    apply_image_to_node(img_tex_5_node, os.path.join(texture_directory, tex_names[4]))
                    apply_image_to_node(img_tex_6_node, os.path.join(texture_directory, tex_names[5]))
                    apply_image_to_node(img_tex_7_node, os.path.join(texture_directory, tex_names[6]))
                    apply_image_to_node(img_tex_8_node, os.path.join(texture_directory, tex_names[7]))
                    print(f"Currently unsupported amount of textures. Renaming of files will still occur but no shader details will be setup.")
                    
                    rename_images(img_tex_1_node, tex_names[0])
                    rename_images(img_tex_2_node, tex_names[1])
                    rename_images(img_tex_3_node, tex_names[2])
                    rename_images(img_tex_4_node, tex_names[3])
                    rename_images(img_tex_5_node, tex_names[4])
                    rename_images(img_tex_6_node, tex_names[5])
                    rename_images(img_tex_7_node, tex_names[6])
                    rename_images(img_tex_8_node, tex_names[7])
                    
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])
                    if is_texture_encrypted(img_tex_3_node) and tex_names[2] not in encrypted_textures:
                        ini_error_text += f'{tex_names[2]} is encrypted. \n'
                        encrypted_textures.append(tex_names[2])
                    if is_texture_encrypted(img_tex_4_node) and tex_names[3] not in encrypted_textures:
                        ini_error_text += f'{tex_names[3]} is encrypted. \n'
                        encrypted_textures.append(tex_names[3])
                    if is_texture_encrypted(img_tex_5_node) and tex_names[4] not in encrypted_textures:
                        ini_error_text += f'{tex_names[4]} is encrypted. \n'
                        encrypted_textures.append(tex_names[4])
                    if is_texture_encrypted(img_tex_6_node) and tex_names[5] not in encrypted_textures:
                        ini_error_text += f'{tex_names[5]} is encrypted. \n'
                        encrypted_textures.append(tex_names[5])
                    if is_texture_encrypted(img_tex_7_node) and tex_names[6] not in encrypted_textures:
                        ini_error_text += f'{tex_names[6]} is encrypted. \n'
                        encrypted_textures.append(tex_names[6])
                    if is_texture_encrypted(img_tex_8_node) and tex_names[7] not in encrypted_textures:
                        ini_error_text += f'{tex_names[7]} is encrypted. \n'
                        encrypted_textures.append(tex_names[7])
                    
                if int(_currentTextureCount) == 9:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))
                    apply_image_to_node(img_tex_3_node, os.path.join(texture_directory, tex_names[2]))
                    apply_image_to_node(img_tex_4_node, os.path.join(texture_directory, tex_names[3]))
                    apply_image_to_node(img_tex_5_node, os.path.join(texture_directory, tex_names[4]))
                    apply_image_to_node(img_tex_6_node, os.path.join(texture_directory, tex_names[5]))
                    apply_image_to_node(img_tex_7_node, os.path.join(texture_directory, tex_names[6]))
                    apply_image_to_node(img_tex_8_node, os.path.join(texture_directory, tex_names[7]))
                    apply_image_to_node(img_tex_9_node, os.path.join(texture_directory, tex_names[8]))
                    print(f"Currently unsupported amount of textures. Renaming of files will still occur but no shader details will be setup.")
                    
                    rename_images(img_tex_1_node, tex_names[0])
                    rename_images(img_tex_2_node, tex_names[1])
                    rename_images(img_tex_3_node, tex_names[2])
                    rename_images(img_tex_4_node, tex_names[3])
                    rename_images(img_tex_5_node, tex_names[4])
                    rename_images(img_tex_6_node, tex_names[5])
                    rename_images(img_tex_7_node, tex_names[6])
                    rename_images(img_tex_8_node, tex_names[7])
                    rename_images(img_tex_9_node, tex_names[8])
                    
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])
                    if is_texture_encrypted(img_tex_3_node) and tex_names[2] not in encrypted_textures:
                        ini_error_text += f'{tex_names[2]} is encrypted. \n'
                        encrypted_textures.append(tex_names[2])
                    if is_texture_encrypted(img_tex_4_node) and tex_names[3] not in encrypted_textures:
                        ini_error_text += f'{tex_names[3]} is encrypted. \n'
                        encrypted_textures.append(tex_names[3])
                    if is_texture_encrypted(img_tex_5_node) and tex_names[4] not in encrypted_textures:
                        ini_error_text += f'{tex_names[4]} is encrypted. \n'
                        encrypted_textures.append(tex_names[4])
                    if is_texture_encrypted(img_tex_6_node) and tex_names[5] not in encrypted_textures:
                        ini_error_text += f'{tex_names[5]} is encrypted. \n'
                        encrypted_textures.append(tex_names[5])
                    if is_texture_encrypted(img_tex_7_node) and tex_names[6] not in encrypted_textures:
                        ini_error_text += f'{tex_names[6]} is encrypted. \n'
                        encrypted_textures.append(tex_names[6])
                    if is_texture_encrypted(img_tex_8_node) and tex_names[7] not in encrypted_textures:
                        ini_error_text += f'{tex_names[7]} is encrypted. \n'
                        encrypted_textures.append(tex_names[7])
                    if is_texture_encrypted(img_tex_9_node) and tex_names[8] not in encrypted_textures:
                        ini_error_text += f'{tex_names[8]} is encrypted. \n'
                        encrypted_textures.append(tex_names[8])
                    
                if int(_currentTextureCount) == 10:
                    # verify that each node needed has an image. Cause thats important. 
                    apply_image_to_node(img_tex_1_node, os.path.join(texture_directory, tex_names[0]))
                    apply_image_to_node(img_tex_2_node, os.path.join(texture_directory, tex_names[1]))
                    apply_image_to_node(img_tex_3_node, os.path.join(texture_directory, tex_names[2]))
                    apply_image_to_node(img_tex_4_node, os.path.join(texture_directory, tex_names[3]))
                    apply_image_to_node(img_tex_5_node, os.path.join(texture_directory, tex_names[4]))
                    apply_image_to_node(img_tex_6_node, os.path.join(texture_directory, tex_names[5]))
                    apply_image_to_node(img_tex_7_node, os.path.join(texture_directory, tex_names[6]))
                    apply_image_to_node(img_tex_8_node, os.path.join(texture_directory, tex_names[7]))
                    apply_image_to_node(img_tex_9_node, os.path.join(texture_directory, tex_names[8]))
                    apply_image_to_node(img_tex_10_node, os.path.join(texture_directory, tex_names[9]))
                    print(f"Currently unsupported amount of textures. Renaming of files will still occur but no shader details will be setup.")
                    
                    rename_images(img_tex_1_node, tex_names[0])
                    rename_images(img_tex_2_node, tex_names[1])
                    rename_images(img_tex_3_node, tex_names[2])
                    rename_images(img_tex_4_node, tex_names[3])
                    rename_images(img_tex_5_node, tex_names[4])
                    rename_images(img_tex_6_node, tex_names[5])
                    rename_images(img_tex_7_node, tex_names[6])
                    rename_images(img_tex_8_node, tex_names[7])
                    rename_images(img_tex_9_node, tex_names[8])
                    rename_images(img_tex_10_node, tex_names[9])
                    
                    if is_texture_encrypted(img_tex_1_node) and tex_names[0] not in encrypted_textures:
                        ini_error_text += f'{tex_names[0]} is encrypted. \n'
                        encrypted_textures.append(tex_names[0])
                    if is_texture_encrypted(img_tex_2_node) and tex_names[1] not in encrypted_textures:
                        ini_error_text += f'{tex_names[1]} is encrypted. \n'
                        encrypted_textures.append(tex_names[1])
                    if is_texture_encrypted(img_tex_3_node) and tex_names[2] not in encrypted_textures:
                        ini_error_text += f'{tex_names[2]} is encrypted. \n'
                        encrypted_textures.append(tex_names[2])
                    if is_texture_encrypted(img_tex_4_node) and tex_names[3] not in encrypted_textures:
                        ini_error_text += f'{tex_names[3]} is encrypted. \n'
                        encrypted_textures.append(tex_names[3])
                    if is_texture_encrypted(img_tex_5_node) and tex_names[4] not in encrypted_textures:
                        ini_error_text += f'{tex_names[4]} is encrypted. \n'
                        encrypted_textures.append(tex_names[4])
                    if is_texture_encrypted(img_tex_6_node) and tex_names[5] not in encrypted_textures:
                        ini_error_text += f'{tex_names[5]} is encrypted. \n'
                        encrypted_textures.append(tex_names[5])
                    if is_texture_encrypted(img_tex_7_node) and tex_names[6] not in encrypted_textures:
                        ini_error_text += f'{tex_names[6]} is encrypted. \n'
                        encrypted_textures.append(tex_names[6])
                    if is_texture_encrypted(img_tex_8_node) and tex_names[7] not in encrypted_textures:
                        ini_error_text += f'{tex_names[7]} is encrypted. \n'
                        encrypted_textures.append(tex_names[7])
                    if is_texture_encrypted(img_tex_9_node) and tex_names[8] not in encrypted_textures:
                        ini_error_text += f'{tex_names[8]} is encrypted. \n'
                        encrypted_textures.append(tex_names[8])
                    if is_texture_encrypted(img_tex_10_node) and tex_names[9] not in encrypted_textures:
                        ini_error_text += f'{tex_names[9]} is encrypted. \n'
                        encrypted_textures.append(tex_names[9])
                    
                
                print(f"")
            except AttributeError as e:
                print(f"Error processing material '{_currentMatName}': {str(e)}")
                continue
            
    ini_error_text += f'----------------------------------------'
    print(f"{ini_error_text}")
# Operator to rename image data blocks as jpegs. This is due to jpgs being supported image types.

def save_image_as_jpg(node, file_path):
    if not node or not isinstance(node, bpy.types.ShaderNodeTexImage):
        print("Invalid node. Please provide a valid image node.")
        return
    
    if not file_path.lower().endswith(('.jpg', '.jpeg')):
        print("Invalid file path. Please provide a path ending with '.jpg' or '.jpeg'.")
        return
    
    # Get the image from the node
    image = node.image
    
    if not image:
        print("No image data found in the node.")
        return
    
    # Set the output file format to JPEG
    bpy.context.scene.render.image_settings.file_format = 'JPEG'
    
    # Save the image
    image.save_render(filepath=file_path)
    print(f"Image saved as {file_path}")


# The operator for renaming image files in the shader graph

def rename_images(node, newname):
    if node is not None and node.image is not None:
        filepath = bpy.path.abspath(node.image.filepath)
        directory, filename = os.path.split(filepath)
        new_directory = os.path.join(directory, "texture")
        parent_directory = os.path.basename(os.path.dirname(directory))
        new_base, new_ext = os.path.splitext(newname)
        
        if parent_directory == "texture":
            #print(f"Skipping renaming as the file is already in 'textures' directory: {filepath}")
            return
        
        if newname is not None:
            updated_filepath = os.path.join(new_directory, newname)
            
            # Check if the original filename is the same as the new name
            if filename == newname:
                #print("Original filename is the same as the new name. Skipping renaming.")
                return
                
            # Check if the original filename is the same as the new name
            if os.path.exists(updated_filepath):
                print("File already moved. Skipping renaming, and assigning new image.")
                
                # Set the image node file path to the new file path
                node.image.filepath = updated_filepath
                
                # Set the name of the image node to the new file name
                node.image.name = newname
                
                # Reload the image
                node.image.reload()
                return
            
            # Create the directory if it doesn't exist
            os.makedirs(new_directory, exist_ok=True)
            
            print(f"Original filepath: {filepath}.")
            print(f"New filepath: {updated_filepath}.")
            if os.path.exists(filepath):
                # If the new file is a png, we need to convert the dds to png else it will be corrupted
                if new_ext.lower() == '.png':
                    # Perform the conversion
                    img = node.image  # Get the current image data block
                    
                    # Prepare to create new image
                    width, height = img.size[:]
                    pixels = list(img.pixels)  # Copy original pixel data
                    
                    # Prepare pixel data for two new images
                    img_pixels = []
                    
                    # Iterate through the original image pixel data
                    num_channels = 4  # RGBA
                    for i in range(0, len(pixels), num_channels):
                        r, g, b, a = pixels[i:i+num_channels]
                        
                        # For the RGB image, ignore the alpha channel
                        img_pixels.extend([r, g, b, a])  # Normal file but png
                    
                    # Create a new image file
                    new_image = bpy.data.images.new(name=newname, width=width, height=height)
                    new_image.filepath = updated_filepath  # Set the filepath for the new image
                    
                    # Assign pixel data to the new image
                    new_image.pixels = img_pixels
                    new_image.file_format = 'PNG'
                    
                    # Save the image data as a new image on disc with the updated file path
                    new_image.save()
                    
                    # Remove the newly created image from bpy.data.images
                    bpy.data.images.remove(new_image)
                elif new_ext.lower() == '.jpg':
                    save_image_as_jpg(node, updated_filepath)
                elif new_ext.lower() == '.jpeg':
                    save_image_as_jpg(node, updated_filepath)
                else:    
                    # Copy original file to the new file path
                    shutil.copy(filepath, updated_filepath)
                
                # Set the image node file path to the new file path
                node.image.filepath = updated_filepath
                
                # Set the name of the image node to the new file name
                node.image.name = newname
                
                # Reload the image
                node.image.reload()
            
        else:
            print(f"Name missing for file, renaming will not occur for {node.name}.")
    else:
        print(f"Filepath missing for {node}, renaming will not occur for {node.name}.")
    

def main_ini_processer(ini_filepath):
    #DEBUG - ini_filepath = "D:/SteamLibrary/steamapps/common/assettocorsa/content/cars/kyu_nissan_s15_msports_kyuspec/kyu_s15_msports_kyu.fbx.ini"
    material_data = custom_ini_parser(ini_filepath)
    apply_material_settings_from_ini(material_data, ini_filepath)