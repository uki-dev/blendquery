import cadquery
import re

# TODO: share with `__init__.py`
TYPE_TO_PROPERTY = {
    "bool": "bool_value",
    "int": "int_value",
    "float": "float_value",
    "str": "str_value",
}


def parse_script(script: str, attributes):
    globals = {
        "cadquery": cadquery,
        "cq": cadquery,
    }
    locals = {}
    # Override attributes
    for attribute in attributes:
        if not attribute.defined:
            continue
        key = attribute.key
        property = TYPE_TO_PROPERTY[attribute.type]
        value = getattr(attribute, property)
        pattern = r'({}\s*=\s*"(.*?)")'.format(re.escape(key))
        script = re.sub(pattern, f'{key} = "{value}"', script)
    exec(script, globals, locals)
    # Ignore all keys that start with `_`, as they are to be considered hidden
    locals = {key: value for key, value in locals.items() if not key.startswith("_")}
    return locals


def map_attributes(locals, attributes):
    for attribute in attributes:
        attribute.defined = attribute.key in locals

    for key in locals:
        value = locals[key]
        type_name = value.__class__.__name__
        if type_name in TYPE_TO_PROPERTY:
            # Find existing property group that matches key and type
            attribute_property_group = next(
                (
                    attribute
                    for attribute in attributes
                    if attribute.key == key and attribute.type == type_name
                ),
                None,
            )
            # Do not add property group if one matching already exists
            if attribute_property_group is not None:
                continue

            attribute_property_group = attributes.add()
            attribute_property_group.key = key
            attribute_property_group.type = type_name
            property = TYPE_TO_PROPERTY[type_name]
            setattr(attribute_property_group, property, value)
