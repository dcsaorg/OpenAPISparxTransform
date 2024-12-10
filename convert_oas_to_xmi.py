import json
import xml.etree.ElementTree as ET
import uuid
import yaml
import datetime
import sys
import os
from openapi_spec_validator import validate_spec
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

# Define namespaces
NSMAP = {'UML': 'omg.org/UML1.3'}
UML_NS = NSMAP['UML']
UML = f'{{{UML_NS}}}'

ET.register_namespace('UML', UML_NS)

def create_xmi_element(tag, attributes):
    """Helper function to create an XML element with attributes."""
    attributes = {k: ('' if v is None else str(v)) for k, v in attributes.items()}
    element = ET.Element(f'{UML}{tag}', attributes)
    return element

def create_tagged_value(tag, attributes):
    """Helper function to create a tagged value element."""
    attributes = {k: ('' if v is None else str(v)) for k, v in attributes.items()}
    element = ET.Element(f'{UML}TaggedValue', attributes)
    return element

def add_tagged_values_to_element(element, tagged_values):
    """Add tagged values to an element."""
    tagged_value_container = element.find(f'{UML}ModelElement.taggedValue')
    if tagged_value_container is None:
        tagged_value_container = ET.SubElement(element, f'{UML}ModelElement.taggedValue')
    for tag, value in tagged_values.items():
        if tag != 'author':  # Skip the author tag
            tagged_value_container.append(create_tagged_value('TaggedValue', {'tag': tag, 'value': ('' if value is None else str(value))}))

def create_class_element(class_name, parent_element, element_id_counter, package_id, description, model_name):
    """Helper function to create a class element."""
    class_id = f'EAID_{str(uuid.uuid4()).replace("-", "_").upper()}'
    class_element = create_xmi_element('Class', {
        'name': class_name,
        'xmi.id': class_id,
        'visibility': 'public',
        'namespace': package_id,
        'isRoot': 'false',
        'isLeaf': 'false',
        'isAbstract': 'false',
        'isActive': 'false'
    })

    class_tagged_values = {
        'isSpecification': 'false',
        'ea_stype': 'Class',
        'ea_ntype': '0',
        'version': '1.0',
        'package': package_id,
        'date_created': datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S'),
        'date_modified': datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S'),
        'gentype': 'Java',
        'tagged': '0',
        'package_name': model_name,
        'phase': '1.0',
        'complexity': '1',
        'status': 'Proposed',
        'tpos': '0',
        'ea_localid': str(next(element_id_counter)),
        'ea_eleType': 'element',
        'ea_guid': f'{{{str(uuid.uuid4())}}}',
        'documentation': description
    }

    add_tagged_values_to_element(class_element, class_tagged_values)
    parent_element.append(class_element)
    return class_element

def parse_schema(schema, parent_element, element_id_counter, class_id_map, class_element, package_namespace_owned_element, model_name, containing_class=None):
    """Recursively parse a JSON schema and add to the XML tree."""
    classifier_feature = ET.SubElement(class_element, f'{UML}Classifier.feature')

    for property_name, property_schema in schema.get('properties', {}).items():
        attribute_id = f'attr_{next(element_id_counter)}'
        attribute_element = create_xmi_element('Attribute', {
            'name': property_name,
            'xmi.id': attribute_id,
            'visibility': 'private',
            'changeable': 'none',
            'ownerScope': 'instance',
            'targetScope': 'instance'
        })

        if 'example' in property_schema:
            initial_value = property_schema['example']
            initial_value_element = create_xmi_element('Attribute.initialValue', {})
            expression_element = create_xmi_element('Expression', {'body': str(initial_value)})
            initial_value_element.append(expression_element)
            attribute_element.append(initial_value_element)

        type_value = property_schema.get('type', 'string')
        format_value = property_schema.get('format', '')

        if '$ref' in property_schema:
            ref_class_name = property_schema['$ref'].split('/')[-1]
            format_value = ref_class_name
            type_value = 'object'

        if 'oneOf' in property_schema:
            ref_classes = handle_schema_composition(property_schema['oneOf'], containing_class, parent_element, element_id_counter, class_id_map, package_namespace_owned_element, parent_element.get('namespace'), model_name)
            format_value = 'oneOf ' + ', '.join(ref_classes)
            type_value = 'object'
        elif 'allOf' in property_schema:
            ref_classes = handle_schema_composition(property_schema['allOf'], containing_class, parent_element, element_id_counter, class_id_map, package_namespace_owned_element, parent_element.get('namespace'), model_name)
            format_value = 'allOf ' + ', '.join(ref_classes)
            type_value = 'object'
        elif 'anyOf' in property_schema:
            ref_classes = handle_schema_composition(property_schema['anyOf'], containing_class, parent_element, element_id_counter, class_id_map, package_namespace_owned_element, parent_element.get('namespace'), model_name)
            format_value = 'anyOf ' + ', '.join(ref_classes)
            type_value = 'object'

        if type_value == 'array' and 'items' in property_schema:
            item_schema = property_schema['items']
            if '$ref' in item_schema:
                ref_class_name = item_schema['$ref'].split('/')[-1]
                format_value = f'Array of {ref_class_name}'
            else:
                item_type = item_schema.get('type', 'string')
                format_value = f'Array of {item_type}'

        if type_value == 'string' and not format_value and 'maxLength' in property_schema:
            # Set format as "string(maxLength)"
            format_value = f"string({property_schema['maxLength']})"

        type_element = create_xmi_element('StructuralFeature.type', {})
        type_classifier = create_xmi_element('Classifier', {'xmi.idref': 'eaxmiid0'})  # Placeholder for actual type resolution
        type_element.append(type_classifier)
        attribute_element.append(type_element)

        attribute_tagged_values = {
            'type': type_value,
            'style': format_value,
            'ea_guid': f'{{{str(uuid.uuid4())}}}',
            'ea_localid': str(next(element_id_counter)),
            'styleex': 'volatile=0;',
            'description': property_schema.get('description', '')
        }
        add_tagged_values_to_element(attribute_element, attribute_tagged_values)
        classifier_feature.append(attribute_element)

def handle_schema_composition(composition_list, containing_class, parent_element, element_id_counter, class_id_map, package_namespace_owned_element, top_level_package_id, model_name):
    """Handle schema composition (oneOf, allOf, anyOf) and generate inner classes if necessary."""
    ref_classes = []
    for ref in composition_list:
        if '$ref' in ref:
            ref_classes.append(ref['$ref'].split('/')[-1])
        elif 'title' in ref:
            inline_class_name = f"{containing_class}.{ref['title']}" if containing_class else ref['title']
            ref_classes.append(inline_class_name)
            inline_class_element = create_class_element(inline_class_name, package_namespace_owned_element, element_id_counter, top_level_package_id, ref.get('description', ''), model_name)
            class_id_map[inline_class_name] = {'id': inline_class_element.get('xmi.id'), 'element': inline_class_element}
            parse_schema(ref, parent_element, element_id_counter, class_id_map, inline_class_element, package_namespace_owned_element, model_name, containing_class=inline_class_name)
    return ref_classes

def json_to_xmi(spec, model_name, ea_root_class_name):
    """Convert JSON specification to XMI format."""
    xmi_root = ET.Element('XMI', {
        'xmi.version': '1.1',
        'timestamp': datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S')
    })
    
    xmi_header = ET.SubElement(xmi_root, 'XMI.header')
    xmi_documentation = ET.SubElement(xmi_header, 'XMI.documentation')
    ET.SubElement(xmi_documentation, 'XMI.exporter').text = 'Enterprise Architect'
    ET.SubElement(xmi_documentation, 'XMI.exporterVersion').text = '2.5'
    ET.SubElement(xmi_documentation, 'XMI.exporterID').text = '1628'

    xmi_content = ET.SubElement(xmi_root, 'XMI.content')
    uml_model = create_xmi_element('Model', {
        'name': 'EA Model',
        'xmi.id': f'MX_{str(uuid.uuid4()).replace("-", "_").upper()}'
    })
    xmi_content.append(uml_model)

    model_namespace_owned_element = create_xmi_element('Namespace.ownedElement', {})
    uml_model.append(model_namespace_owned_element)

    # Add EARootClass with generated UUID
    ea_root_class = create_xmi_element('Class', {
        'name': ea_root_class_name,
        'xmi.id': f'EAID_{str(uuid.uuid4()).replace("-", "_").upper()}',
        'isRoot': 'true',
        'isLeaf': 'false',
        'isAbstract': 'false'
    })
    model_namespace_owned_element.append(ea_root_class)

    # Add OpenAPIModel package
    openapi_model_package = create_xmi_element('Package', {
        'name': model_name,
        'xmi.id': f'EAPK_{str(uuid.uuid4()).replace("-", "_").upper()}',
        'isRoot': 'false',
        'isLeaf': 'false',
        'isAbstract': 'false',
        'visibility': 'public'
    })
    model_namespace_owned_element.append(openapi_model_package)

    current_datetime = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S')
    openapi_model_tagged_values = {
        'parent': openapi_model_package.get('xmi.id'),
        'modified': current_datetime,
        'version': '1.0',
        'batchsave': '0',
        'batchload': '0',
        'phase': '1.0',
        'status': 'Proposed',
        'complexity': '1',
        'ea_stype': 'Public'
    }
    add_tagged_values_to_element(openapi_model_package, openapi_model_tagged_values)

    package_namespace_owned_element = create_xmi_element('Namespace.ownedElement', {})
    openapi_model_package.append(package_namespace_owned_element)

    class_id_map = {}
    element_id_counter = iter(range(1, 1000000))

    # Parse components.schemas to generate classes
    components = spec.get('components', {})
    schemas = components.get('schemas', {})
    for schema_name, schema in schemas.items():
        class_element = create_class_element(schema_name, package_namespace_owned_element, element_id_counter, openapi_model_package.get('xmi.id'), schema.get('description', ''), model_name)
        class_id_map[schema_name] = {'id': class_element.get('xmi.id'), 'element': class_element}
        parse_schema(schema, class_element, element_id_counter, class_id_map, class_element, package_namespace_owned_element, model_name, containing_class=schema_name)

    # Handle dependencies for schema composition
    for schema_name, schema in schemas.items():
        class_info = class_id_map.get(schema_name)
        if class_info:
            if 'oneOf' in schema or 'allOf' in schema or 'anyOf' in schema:
                ref_classes = []
                composition_type = ''
                if 'oneOf' in schema:
                    ref_classes = handle_schema_composition(schema['oneOf'], schema_name, package_namespace_owned_element, element_id_counter, class_id_map, package_namespace_owned_element, openapi_model_package.get('xmi.id'), model_name)
                    composition_type = 'oneOf'
                elif 'allOf' in schema:
                    ref_classes = handle_schema_composition(schema['allOf'], schema_name, package_namespace_owned_element, element_id_counter, class_id_map, package_namespace_owned_element, openapi_model_package.get('xmi.id'), model_name)
                    composition_type = 'allOf'
                elif 'anyOf' in schema:
                    ref_classes = handle_schema_composition(schema['anyOf'], schema_name, package_namespace_owned_element, element_id_counter, class_id_map, package_namespace_owned_element, openapi_model_package.get('xmi.id'), model_name)
                    composition_type = 'anyOf'
                
                alias_value = f'{composition_type} ' + ', '.join(ref_classes)
                alias_tagged_value = create_tagged_value('TaggedValue', {'tag': 'alias', 'value': alias_value})
                class_tagged_value_container = class_info['element'].find(f'.//{UML}ModelElement.taggedValue')
                if class_tagged_value_container is None:
                    class_tagged_value_container = ET.SubElement(class_info['element'], f'{UML}ModelElement.taggedValue')
                class_tagged_value_container.append(alias_tagged_value)

    xmi_root.append(ET.Element('XMI.difference'))
    xmi_root.append(ET.Element('XMI.extensions', {'xmi.extender': 'Enterprise Architect 2.5'}))

    return xmi_root

def main():
    if len(sys.argv) < 3:
        print("Usage: python convert_json_to_xmi.py <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # Extract filename without extension for dynamic naming
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    model_name = f"OAS_{base_name}"
    ea_root_class_name = f"EARootClass_{base_name}"

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            if input_file.endswith('.yaml') or input_file.endswith('.yml'):
                spec = yaml.safe_load(f)
            else:
                spec = json.load(f)
        validate_spec(spec)
        print("OpenAPI specification is valid.")
    except (yaml.YAMLError, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading input file: {e}")
        sys.exit(1)
    except OpenAPIValidationError as e:
        print(f"OpenAPI specification validation error: {e}")
        sys.exit(1)

    xmi_tree = ET.ElementTree(json_to_xmi(spec, model_name, ea_root_class_name))
    try:
        xmi_tree.write(output_file, encoding='utf-8', xml_declaration=True)
        print(f"XMI file written to {output_file}")
    except IOError as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
