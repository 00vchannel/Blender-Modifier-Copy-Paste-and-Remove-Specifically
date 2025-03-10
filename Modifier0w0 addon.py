import bpy
from bpy.types import Panel, Operator
from bpy.props import EnumProperty, BoolProperty, CollectionProperty, StringProperty

# Store the copied modifiers
copied_modifiers = []

# Register the addon in Blender 4.0 and above
bl_info = {
    "name": "Modifier0w0",
    "author": "00vchannel",
    "version": (1, 2),
    "blender": (4, 1, 0),
    "location": "3D View > Sidebar > Modifier0w0",
    "description": "Copy, paste, and remove modifiers across multiple objects",
    "category": "Object",
}

# Helper function to handle various property types for copying
def get_property_value(obj, prop_name):
    value = getattr(obj, prop_name)
    
    # Handle different property types
    if hasattr(value, "to_list"):
        return value.to_list()  # For vectors, colors, etc.
    elif hasattr(value, "copy"):
        try:
            return value.copy()  # For collections that can be copied
        except:
            return str(value)  # Fallback to string representation
    
    # Special handling for pointers to other data
    if hasattr(value, "name") and hasattr(value, "id_data"):
        # Store name and data type for later lookup
        data_type = type(value).__name__
        return {"__dataref__": True, "name": value.name, "type": data_type}
    
    return value

# Helper function to set property value with type handling
def set_property_value(obj, prop_name, value):
    # Skip known problematic properties
    if prop_name in {"is_override_data", "rna_type", "active"}:
        return
    
    # Handle data references
    if isinstance(value, dict) and value.get("__dataref__"):
        data_type = value.get("type")
        name = value.get("name")
        
        # Try to find the referenced data
        if data_type == "Object" and name in bpy.data.objects:
            setattr(obj, prop_name, bpy.data.objects[name])
        elif data_type == "VertexGroup" and hasattr(obj.id_data, "vertex_groups") and name in obj.id_data.vertex_groups:
            setattr(obj, prop_name, obj.id_data.vertex_groups[name])
        # Add more types as needed
        
        return
    
    # Handle other types
    try:
        if hasattr(getattr(obj, prop_name), "from_list") and isinstance(value, list):
            getattr(obj, prop_name).from_list(value)
        else:
            setattr(obj, prop_name, value)
    except (AttributeError, TypeError):
        # Silently ignore properties that can't be set
        pass

# Property class for the modifier checkboxes
class ModifierItem(bpy.types.PropertyGroup):
    name: StringProperty()
    enabled: BoolProperty(default=True)

# Get unique modifier types from selected objects
def get_unique_modifier_types(context):
    mod_types = set()
    for obj in context.selected_objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            mod_types.add(mod.type)
    return sorted(list(mod_types))

# Function to get all modifiers of a specific type across selected objects
def get_modifiers_by_type(context, mod_type):
    modifiers = []
    for obj in context.selected_objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == mod_type:
                modifiers.append((obj, mod))
    return modifiers

# Get unique modifier names from selected objects
def get_unique_modifier_names(context):
    mod_names = set()
    for obj in context.selected_objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            mod_names.add(mod.name)
    return sorted(list(mod_names))

class OBJECT_OT_copy_multiple_modifiers(Operator):
    """Copy multiple modifiers from the selected object"""
    bl_idname = "object.copy_multiple_modifiers"
    bl_label = "Copy Multiple Modifiers"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and len(context.active_object.modifiers) > 0
    
    def invoke(self, context, event):
        # Create the modifiers list
        wm = context.window_manager
        if not hasattr(wm, "modifier_list"):
            bpy.types.WindowManager.modifier_list = CollectionProperty(type=ModifierItem)
        
        # Clear previous entries
        wm.modifier_list.clear()
        
        # Add all modifiers from the active object
        for mod in context.active_object.modifiers:
            item = wm.modifier_list.add()
            item.name = mod.name
            item.enabled = True
        
        # Show dialog to let user select modifiers
        return context.window_manager.invoke_props_dialog(self, width=300)
    
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        
        if len(wm.modifier_list) == 0:
            layout.label(text="No modifiers available")
            return
            
        layout.label(text="Select modifiers to copy:")
        
        # Display all modifiers with checkboxes
        for idx, item in enumerate(wm.modifier_list):
            row = layout.row()
            row.prop(item, "enabled", text="")
            mod = context.active_object.modifiers.get(item.name)
            if mod:
                row.label(text=f"{item.name} ({mod.type})")
            else:
                row.label(text=item.name)
    
    def execute(self, context):
        global copied_modifiers
        wm = context.window_manager
        
        # Clear previous copied modifiers
        copied_modifiers = []
        
        # Copy selected modifiers
        for item in wm.modifier_list:
            if item.enabled and item.name in context.active_object.modifiers:
                modifier = context.active_object.modifiers[item.name]
                
                # Store modifier type and properties
                mod_data = {
                    'type': modifier.type,
                    'name': modifier.name,
                    'properties': {},
                    'source_object': context.active_object.name
                }
                
                # Save modifier properties with improved property handling
                for prop in dir(modifier):
                    # Skip built-in attributes and methods
                    if prop.startswith('__') or prop.startswith('bl_') or prop == 'type':
                        continue
                        
                    # Skip known read-only properties
                    if prop in {"is_override_data", "rna_type"}:
                        continue
                        
                    try:
                        # Get property with type handling
                        value = get_property_value(modifier, prop)
                        
                        # Only store non-callable attributes
                        if not callable(value):
                            mod_data['properties'][prop] = value
                    except:
                        pass
                
                copied_modifiers.append(mod_data)
        
        count = len(copied_modifiers)
        if count > 0:
            self.report({'INFO'}, f"Copied {count} modifier{'s' if count > 1 else ''}")
        else:
            self.report({'WARNING'}, "No modifiers were selected for copying")
            
        return {'FINISHED'}

class OBJECT_OT_paste_multiple_modifiers(Operator):
    """Paste all copied modifiers to the selected object"""
    bl_idname = "object.paste_multiple_modifiers"
    bl_label = "Paste All Modifiers"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and len(copied_modifiers) > 0
    
    def execute(self, context):
        global copied_modifiers
        
        # Check if there are copied modifiers
        if not copied_modifiers:
            self.report({'ERROR'}, "No modifiers have been copied")
            return {'CANCELLED'}
        
        # Apply to all selected objects
        objects_modified = 0
        modifiers_added = 0
        
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
                
            obj_mods_added = 0
            for mod_data in copied_modifiers:
                # Add the same type of modifier
                try:
                    new_modifier = obj.modifiers.new(
                        name=mod_data['name'],
                        type=mod_data['type']
                    )
                    
                    # Set modifier properties with improved handling
                    for prop, value in mod_data['properties'].items():
                        try:
                            set_property_value(new_modifier, prop, value)
                        except:
                            pass
                    
                    obj_mods_added += 1
                except:
                    self.report({'WARNING'}, f"Failed to paste modifier: {mod_data['name']} to {obj.name}")
            
            if obj_mods_added > 0:
                objects_modified += 1
                modifiers_added += obj_mods_added
        
        self.report({'INFO'}, f"Pasted {modifiers_added} modifier{'s' if modifiers_added > 1 else ''} to {objects_modified} object{'s' if objects_modified > 1 else ''}")
        return {'FINISHED'}

# Keep the single modifier copy for convenience
class OBJECT_OT_copy_specific_modifier(Operator):
    """Copy a specific modifier from the selected object"""
    bl_idname = "object.copy_specific_modifier"
    bl_label = "Copy Single Modifier"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Function for dynamic enum items
    def get_modifier_enum_items(self, context):
        items = []
        if context.active_object:
            for mod in context.active_object.modifiers:
                items.append((mod.name, mod.name, f"Copy modifier {mod.name}"))
        return items if items else [("NONE", "No Modifiers", "This object has no modifiers")]
    
    # Use external function as item source
    modifier_name: EnumProperty(
        name="Select Modifier",
        description="Choose which modifier to copy",
        items=get_modifier_enum_items
    )
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and len(context.active_object.modifiers) > 0
    
    def invoke(self, context, event):
        # Check if the object has modifiers
        if not context.active_object.modifiers:
            self.report({'ERROR'}, "Selected object has no modifiers")
            return {'CANCELLED'}
        
        # Show dialog to let user select a modifier
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        global copied_modifiers
        
        # Check if a valid modifier is selected
        if self.modifier_name == "NONE":
            self.report({'ERROR'}, "No modifiers available")
            return {'CANCELLED'}
        
        if self.modifier_name not in context.active_object.modifiers:
            self.report({'ERROR'}, "Selected modifier not found")
            return {'CANCELLED'}
        
        modifier = context.active_object.modifiers[self.modifier_name]
        
        # Store modifier type and properties
        mod_data = {
            'type': modifier.type,
            'name': modifier.name,
            'properties': {},
            'source_object': context.active_object.name  # Store source object name
        }
        
        # Save modifier properties with improved property handling
        for prop in dir(modifier):
            # Skip built-in attributes and methods
            if prop.startswith('__') or prop.startswith('bl_') or prop == 'type':
                continue
                
            # Skip known read-only properties
            if prop in {"is_override_data", "rna_type"}:
                continue
                
            try:
                # Get property with type handling
                value = get_property_value(modifier, prop)
                
                # Only store non-callable attributes
                if not callable(value):
                    mod_data['properties'][prop] = value
            except:
                pass
        
        # Store as a single item in the array
        copied_modifiers = [mod_data]
        self.report({'INFO'}, f"Copied modifier: {modifier.name}")
        return {'FINISHED'}

class OBJECT_OT_remove_modifier_by_name(Operator):
    """Remove a specific modifier by name from all selected objects"""
    bl_idname = "object.remove_modifier_by_name"
    bl_label = "Remove Modifier by Name"
    bl_options = {'REGISTER', 'UNDO'}
    
    def get_modifier_names(self, context):
        names = get_unique_modifier_names(context)
        items = [(name, name, f"Remove all modifiers named {name}") for name in names]
        return items if items else [("NONE", "No Modifiers", "No modifiers found in selected objects")]
    
    modifier_name: EnumProperty(
        name="Select Modifier Name",
        description="Choose which modifier name to remove",
        items=get_modifier_names
    )
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0
    
    def invoke(self, context, event):
        # Show dialog to let user select a modifier
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        if self.modifier_name == "NONE":
            self.report({'ERROR'}, "No modifiers available")
            return {'CANCELLED'}
        
        count = 0
        objects_modified = 0
        
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
                
            if self.modifier_name in obj.modifiers:
                obj.modifiers.remove(obj.modifiers[self.modifier_name])
                count += 1
                objects_modified += 1
        
        if count > 0:
            self.report({'INFO'}, f"Removed {count} modifier{'s' if count > 1 else ''} named '{self.modifier_name}' from {objects_modified} object{'s' if objects_modified > 1 else ''}")
        else:
            self.report({'WARNING'}, f"No modifiers named '{self.modifier_name}' found in selected objects")
            
        return {'FINISHED'}

class OBJECT_OT_remove_modifier_by_type(Operator):
    """Remove all modifiers of a specific type from all selected objects"""
    bl_idname = "object.remove_modifier_by_type"
    bl_label = "Remove Modifier by Type"
    bl_options = {'REGISTER', 'UNDO'}
    
    def get_modifier_types(self, context):
        types = get_unique_modifier_types(context)
        items = [(t, t, f"Remove all {t} modifiers") for t in types]
        return items if items else [("NONE", "No Modifiers", "No modifiers found in selected objects")]
    
    modifier_type: EnumProperty(
        name="Select Modifier Type",
        description="Choose which type of modifier to remove",
        items=get_modifier_types
    )
    
    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0
    
    def invoke(self, context, event):
        # Show dialog to let user select a modifier type
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        if self.modifier_type == "NONE":
            self.report({'ERROR'}, "No modifiers available")
            return {'CANCELLED'}
        
        count = 0
        objects_modified = 0
        
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            
            obj_modified = False
            # We need to create a list because we'll be modifying the collection
            mods_to_remove = [mod for mod in obj.modifiers if mod.type == self.modifier_type]
            
            for mod in mods_to_remove:
                obj.modifiers.remove(mod)
                count += 1
                obj_modified = True
            
            if obj_modified:
                objects_modified += 1
        
        if count > 0:
            self.report({'INFO'}, f"Removed {count} {self.modifier_type} modifier{'s' if count > 1 else ''} from {objects_modified} object{'s' if objects_modified > 1 else ''}")
        else:
            self.report({'WARNING'}, f"No {self.modifier_type} modifiers found in selected objects")
            
        return {'FINISHED'}

class VIEW3D_PT_modifier_copy_paste(Panel):
    """Modifier Copy Paste Panel"""
    bl_label = "Modifier Copy Paste"
    bl_idname = "VIEW3D_PT_modifier_copy_paste"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Modifier Copy Paste'
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    
    def draw(self, context):
        layout = self.layout
        
        # Copy section
        box = layout.box()
        box.label(text="Copy Modifiers", icon='COPYDOWN')
        col = box.column(align=True)
        col.operator("object.copy_multiple_modifiers", text="Copy Multiple Modifiers", icon='MODIFIER')
        col.operator("object.copy_specific_modifier", text="Copy Single Modifier", icon='MODIFIER')
        
        # Paste section
        box = layout.box()
        box.label(text="Paste Modifiers", icon='PASTEDOWN')
        col = box.column(align=True)
        col.operator("object.paste_multiple_modifiers", text="Paste All Modifiers", icon='MODIFIER')
        
        # Remove section - NEW
        box = layout.box()
        box.label(text="Remove Modifiers", icon='X')
        col = box.column(align=True)
        col.operator("object.remove_modifier_by_name", text="Remove by Name", icon='CANCEL')
        col.operator("object.remove_modifier_by_type", text="Remove by Type", icon='CANCEL')
        
        # Display information about the currently copied modifiers
        if copied_modifiers:
            box = layout.box()
            box.label(text=f"Copied Modifiers: {len(copied_modifiers)}", icon='INFO')
            
            # Show list of copied modifiers
            if len(copied_modifiers) > 0:
                col = box.column(align=True)
                for mod in copied_modifiers:
                    col.label(text=f"• {mod['name']} ({mod['type']})")
                    
            # Warning for specific types
            has_special_types = any(mod['type'] in {'ARMATURE', 'VERTEX_WEIGHT_EDIT', 
                                              'VERTEX_WEIGHT_MIX', 'MIRROR'} 
                               for mod in copied_modifiers)
            if has_special_types:
                box.label(text="Note: Some modifiers may need manual adjustment", icon='ERROR')

def register():
    bpy.utils.register_class(ModifierItem)
    bpy.utils.register_class(OBJECT_OT_copy_multiple_modifiers)
    bpy.utils.register_class(OBJECT_OT_paste_multiple_modifiers)
    bpy.utils.register_class(OBJECT_OT_copy_specific_modifier)
    bpy.utils.register_class(OBJECT_OT_remove_modifier_by_name)
    bpy.utils.register_class(OBJECT_OT_remove_modifier_by_type)
    bpy.utils.register_class(VIEW3D_PT_modifier_copy_paste)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_modifier_copy_paste)
    bpy.utils.unregister_class(OBJECT_OT_remove_modifier_by_type)
    bpy.utils.unregister_class(OBJECT_OT_remove_modifier_by_name)
    bpy.utils.unregister_class(OBJECT_OT_copy_specific_modifier)
    bpy.utils.unregister_class(OBJECT_OT_paste_multiple_modifiers)
    bpy.utils.unregister_class(OBJECT_OT_copy_multiple_modifiers)
    bpy.utils.unregister_class(ModifierItem)
    
    # Clean up property
    if hasattr(bpy.types.WindowManager, "modifier_list"):
        del bpy.types.WindowManager.modifier_list

if __name__ == "__main__":
    register()