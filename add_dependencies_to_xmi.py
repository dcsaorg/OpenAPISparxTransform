import xml.etree.ElementTree as ET
import uuid
import sys
from collections import defaultdict

# Define namespaces
NSMAP = {'UML': 'omg.org/UML1.3'}
UML_NS = NSMAP['UML']
UML = f'{{{UML_NS}}}'

ET.register_namespace('UML', UML_NS)

# Generate UUID
def generate_uuid():
    return str(uuid.uuid4()).upper()

# Create Dependency Element
def create_dependency_element(client_id, supplier_id, client_name, supplier_name, name=None, multiplicity=None, attr_guid=None):
    dependency_id = f"EAID_{generate_uuid()}"
    dependency_attrs = {
        'xmi.id': dependency_id,
        'client': client_id,
        'supplier': supplier_id
    }

    if name:
        dependency_attrs['name'] = name

    dependency = ET.Element(f'{UML}Dependency', dependency_attrs)

    model_element = ET.SubElement(dependency, f'{UML}ModelElement.taggedValue')

    tagged_values = [
        ('style', '3'),
        ('ea_type', 'Dependency'),
        ('direction', 'Source -> Destination'),
        ('linemode', '3'),
        ('linecolor', '-1'),
        ('linewidth', '0'),
        ('seqno', '0'),
        ('headStyle', '0'),
        ('lineStyle', '0'),
        ('ea_sourceName', client_name),
        ('ea_targetName', supplier_name),
        ('ea_sourceType', 'Class'),
        ('ea_targetType', 'Class'),
        ('src_visibility', 'Public'),
        ('src_aggregation', '0'),
        ('src_isOrdered', 'false'),
        ('src_targetScope', 'instance'),
        ('src_changeable', 'none'),
        ('src_isNavigable', 'false'),
        ('src_containment', 'Unspecified'),
        ('dst_visibility', 'Public'),
        ('dst_aggregation', '0'),
        ('dst_isOrdered', 'false'),
        ('dst_targetScope', 'instance'),
        ('dst_changeable', 'none'),
        ('dst_isNavigable', 'true'),
        ('dst_containment', 'Unspecified'),
        ('virtualInheritance', '0')
    ]

    for tag, value in tagged_values:
        ET.SubElement(model_element, f'{UML}TaggedValue', {'tag': tag, 'value': value})

    if multiplicity:
        ET.SubElement(model_element, f'{UML}TaggedValue', {'tag': 'src_multiplicity', 'value': '1'})
        ET.SubElement(model_element, f'{UML}TaggedValue', {'tag': 'dst_multiplicity', 'value': '0..*'})
        ET.SubElement(model_element, f'{UML}TaggedValue', {'tag': 'lb', 'value': '1'})
        ET.SubElement(model_element, f'{UML}TaggedValue', {'tag': 'rb', 'value': '0..*'})

    if attr_guid:
        ET.SubElement(model_element, f'{UML}TaggedValue', {'tag': 'styleex', 'value': f'LFSP={{{attr_guid}}}L;'})

    if name:
        ET.SubElement(model_element, f'{UML}TaggedValue', {'tag': 'mt', 'value': name})

    return dependency

# Handle object attribute dependencies (Variant 1)
def handle_object_dependencies(root, classes, namespace_owned_element):
    for cls in root.findall(f".//{UML}Class"):
        class_name = cls.get('name')
        class_id = cls.get('xmi.id')

        for attr in cls.findall(f".//{UML}Attribute"):
            attr_type_tag = attr.find(f".//{UML}TaggedValue[@tag='type']")
            style_tag = attr.find(f".//{UML}TaggedValue[@tag='style']")
            ea_guid_tag = attr.find(f".//{UML}TaggedValue[@tag='ea_guid']")

            if attr_type_tag is not None and style_tag is not None:
                attr_type = attr_type_tag.get('value')
                style_value = style_tag.get('value').strip()
                attr_guid = ea_guid_tag.get('value').strip('{}')

                if attr_type == 'object' and style_value in classes:
                    supplier_id = classes[style_value]['xmi.id']
                    supplier_name = style_value
                    dependency = create_dependency_element(class_id, supplier_id, class_name, supplier_name, attr_guid=attr_guid)
                    namespace_owned_element.append(dependency)

# Handle schema composition attribute dependencies (Variant 2)
def handle_schema_composition_attribute_dependencies(root, classes, namespace_owned_element):
    for cls in root.findall(f".//{UML}Class"):
        class_name = cls.get('name')
        class_id = cls.get('xmi.id')

        for attr in cls.findall(f".//{UML}Attribute"):
            attr_type_tag = attr.find(f".//{UML}TaggedValue[@tag='type']")
            style_tag = attr.find(f".//{UML}TaggedValue[@tag='style']")
            ea_guid_tag = attr.find(f".//{UML}TaggedValue[@tag='ea_guid']")

            if attr_type_tag is not None and style_tag is not None:
                attr_type = attr_type_tag.get('value')
                style_value = style_tag.get('value').strip()
                attr_guid = ea_guid_tag.get('value').strip('{}')

                if style_value.startswith('oneOf'):
                    schema_type = 'oneOf'
                elif style_value.startswith('allOf'):
                    schema_type = 'allOf'
                elif style_value.startswith('anyOf'):
                    schema_type = 'anyOf'
                else:
                    schema_type = None

                if schema_type:
                    target_classes = style_value.replace(schema_type, '').strip().split(',')
                    for target_class in target_classes:
                        target_class = target_class.strip()
                        if target_class in classes:
                            supplier_id = classes[target_class]['xmi.id']
                            supplier_name = target_class
                            dependency = create_dependency_element(class_id, supplier_id, class_name, supplier_name, name=schema_type, attr_guid=attr_guid)
                            namespace_owned_element.append(dependency)

# Handle for array dependencies (Variant 3)
def handle_array_dependencies(root, classes, namespace_owned_element):
    for cls in root.findall(f".//{UML}Class"):
        class_name = cls.get('name')
        class_id = cls.get('xmi.id')

        for attr in cls.findall(f".//{UML}Attribute"):
            attr_type_tag = attr.find(f".//{UML}TaggedValue[@tag='type']")
            style_tag = attr.find(f".//{UML}TaggedValue[@tag='style']")
            ea_guid_tag = attr.find(f".//{UML}TaggedValue[@tag='ea_guid']")

            if attr_type_tag is not None and style_tag is not None:
                attr_type = attr_type_tag.get('value')
                style_value = style_tag.get('value').strip()
                attr_guid = ea_guid_tag.get('value').strip('{}')

                if attr_type == 'array':
                    if style_value.startswith('Array of '):
                        class_name_in_style = style_value.replace('Array of ', '').strip()
                        if class_name_in_style in classes:
                            supplier_id = classes[class_name_in_style]['xmi.id']
                            supplier_name = class_name_in_style
                            dependency = create_dependency_element(class_id, supplier_id, class_name, supplier_name, name='array', multiplicity=True, attr_guid=attr_guid)
                            namespace_owned_element.append(dependency)

# Handle schema composition dependencies at class level
def handle_schema_composition_class_dependencies(root, classes, namespace_owned_element):
    for cls in root.findall(f".//{UML}Class"):
        class_name = cls.get('name')
        class_id = cls.get('xmi.id')

        alias_tag = cls.find(f".//{UML}TaggedValue[@tag='alias']")

        if alias_tag is not None:
            alias_value = alias_tag.get('value').strip()

            if alias_value.startswith('oneOf'):
                schema_type = 'oneOf'
            elif alias_value.startswith('allOf'):
                schema_type = 'allOf'
            elif alias_value.startswith('anyOf'):
                schema_type = 'anyOf'
            else:
                schema_type = None

            if schema_type:
                target_classes = alias_value.replace(schema_type, '').strip().split(',')
                for target_class in target_classes:
                    target_class = target_class.strip()
                    if target_class in classes:
                        supplier_id = classes[target_class]['xmi.id']
                        supplier_name = target_class
                        dependency = create_dependency_element(class_id, supplier_id, class_name, supplier_name, name=schema_type)
                        namespace_owned_element.append(dependency)

# Main function to add dependencies
def add_dependencies(input_file, output_file):
    tree = ET.parse(input_file)
    root = tree.getroot()

    # Find the Namespace.ownedElement to append dependencies
    namespace_owned_element = root.find(f".//{UML}Package//{UML}Namespace.ownedElement")

    classes = {}
    for cls in root.findall(f".//{UML}Class"):
        class_name = cls.get('name')
        classes[class_name] = {'xmi.id': cls.get('xmi.id'), 'name': class_name}

    # Call functions to handle each type of dependency
    handle_object_dependencies(root, classes, namespace_owned_element)
    handle_schema_composition_attribute_dependencies(root, classes, namespace_owned_element)
    handle_array_dependencies(root, classes, namespace_owned_element)
    handle_schema_composition_class_dependencies(root, classes, namespace_owned_element)

    tree.write(output_file, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python add_dependencies_to_xmi.py <input_file> <output_file>")
        sys.exit(1)

    input_xmi_file = sys.argv[1]
    output_xmi_file = sys.argv[2]
    add_dependencies(input_xmi_file, output_xmi_file)
