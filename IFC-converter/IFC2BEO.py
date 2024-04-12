import ifcopenshell
import ifcopenshell.geom
from rdflib import Graph, Namespace, Literal, URIRef
import json
import os

####PARAMETERS
with open('./IFC-converter/config.json', 'r',encoding='utf-8') as fp:
    params =json.load(fp)

# IFC file path
file_path = params['ifc-file-path']
if params['rdf-output']['output-name']: asset_name = params['rdf-output']['output-name']
else: asset_name = file_path.split('/')[-1].split('.')[0]


# load IFC file
file = ifcopenshell.open(file_path)
file_info = os.stat(file_path)
file_size_bytes = file_info.st_size

#load ifcOwl ontology -- when ontology is published read from online url
ifc_graph_path =  "beo.ttl"
print(ifc_graph_path)
ifc_graph = Graph()
ifc_graph.parse(ifc_graph_path, format = 'turtle')

# urls
asset_ref =  URIRef("http://www.carlos-server.test/assets/"+asset_name+"/")
beo_ref =  URIRef("https://w3id.org/beo#")

if params['rdf-output']['output-path'].endswith('/'): save_path = params['rdf-output']['output-path'] + asset_name
else: save_path = params['rdf-output']['output-path'] + '/' + asset_name

### Load IFC schema (EXPRESS)
schema_name = str(file.schema)
schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(file.schema)

# gets object property uris with label X of the entity class and its supertypes
def get_attr_object_property(entity, attr_name): 
    attr_query = """
        SELECT ?property WHERE {{
            {{ ?property rdfs:domain ?superclass .
            <{}> rdfs:subClassOf* ?superclass .
            ?property rdfs:label "{}" .}}
        }}""".format(entity, attr_name)
    
    # Execute the query
    results = ifc_graph.query(attr_query)
    # Print the results
    result  =  [item[0] for item in results]
    return result[0]

# gets object property uris with label X of the entity class and its supertypes
def get_attributes(entity): 
    attr_query = """
        SELECT ?property ?label WHERE {{
            {{ ?property rdfs:domain ?superclass .
            <{}> rdfs:subClassOf* ?superclass .
            ?property rdfs:label ?label}}
            UNION
            {{ ?property rdfs:domain <{}> .
            ?property rdfs:label ?label}}
        }}""".format(entity,entity)
    
    # Execute the query
    results = ifc_graph.query(attr_query)
    # Print the results
    result = {}
    for item in results:
        result[str(item[1])]=item[0]
    return result

def untangle_named_type_declaration(attr_declared_type):
    last_declared_type = attr_declared_type.declared_type()
    if last_declared_type.declared_type().declared_type().as_named_type():
        untangle_named_type_declaration(last_declared_type.declared_type())
    else:
        return last_declared_type.declared_type().declared_type()


# Instantiate  empty  graph for the asset
g  = Graph()

# Create a namespaces
BEO = Namespace(beo_ref)
INST = Namespace(asset_ref)
OMG = Namespace("https://w3id.org/omg#")
FOG = Namespace("https://w3id.org/fog#")
GOM = Namespace("https://w3id.org/gom#")
DCE = Namespace("http://purl.org/dc/elements/1.1/")
VANN = Namespace("http://purl.org/vocab/vann/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")

# Bind your custom prefix
g.bind("beo", BEO)
g.bind('inst', INST)
g.bind('rdf', RDF)
g.bind('rdfs', RDFS)
g.bind('owl', OWL)
g.bind('vann', VANN)
g.bind('dce', DCE)
g.bind('xsd', XSD)
g.bind('omg', OMG)
g.bind('fog', FOG)
g.bind('gom', GOM)

g.add((asset_ref, RDF.type, OWL.Ontology ))
g.add((asset_ref, OWL.imports, beo_ref ))


created_types = {}
created_entities = {}
created_sets = []

type_maps = {}

for declaration in schema.declarations():
    
    if declaration.as_type_declaration(): # map Ifc types to XSD ontology types

        declared_type = declaration.declared_type()

        if declared_type.as_simple_type():
            type = declaration.declared_type().declared_type()
            if type == 'string': type = XSD.string
            elif type == 'real': type = XSD.float
            elif type == 'number': type = XSD.float
            elif type == 'boolean': type = XSD.boolean
            elif type == 'integer': type = XSD.integer
            elif type == 'logical': type = XSD.boolean
            elif type == 'binary': type = XSD.boolean
            else: print(type)
            type_maps[declaration.name()]= type

            
        elif declared_type.as_named_type():
            type = untangle_named_type_declaration(declaration).declared_type()
            if type == 'string': type = XSD.string
            elif type == 'real': type = XSD.float
            elif type == 'number': type = XSD.float
            elif type == 'boolean': type = XSD.boolean
            elif type == 'integer': type = XSD.integer
            elif type == 'logical': type = XSD.boolean
            elif type == 'binary': type = XSD.boolean
            else: print(type)
            type_maps[declaration.name()]=type                

with open('ontology-config.json', 'r',encoding='utf-8') as fp:
    config_file =json.load(fp)

## non-geometrical information

def create_entity(entity)-> URIRef:
    
    # get the  IFC definition of the entity
    entity_schema = schema.declaration_by_name(entity.is_a())

    entity_name = entity_schema.name()

    instance_name = entity_name[3:] + '_' + str(entity.id())

    entity_uri = BEO[config_file[entity_name[3:]]['class_name']]
    instance_uri = INST[instance_name]

    attrs = get_attributes(entity_uri)


    info = entity.get_info()
    if 'PredefinedType' in info.keys() and info['PredefinedType'] in config_file[entity_name[3:]]['enum'].keys() :
        entity_uri = BEO[config_file[entity_name[3:]]['enum'][info['PredefinedType']]['class_name']]


    if instance_uri not in created_entities.keys(): 
        print(instance_uri)
        created_entities[instance_uri] = []

        #create instance
        print(entity_uri)
        g.add((instance_uri, RDF.type, entity_uri))

        #create instance attributes
        attr_count = entity_schema.attribute_count()

        for i in range(attr_count):

            attr =  entity_schema.attribute_by_index(i)
        
            # check that the object referenced and the attribute exists
            try:
                attr_value = entity[i]
            except RuntimeError:
                print("\033[91mThe entity of type {} with id #{} is malformed: referenced {} does not exist in file or is also malformed\033[0m".format(entity.is_a(), entity.id(), entity.attribute_name(i)))
                continue
            
            if not attr_value:
                if not attr.optional():
                    print("\033[91mThe entity of type {} with id #{} is malformed: referenced {} does not exist in file or is also malformed, and is not an optional attribute.\033[0m".format(entity.is_a(), entity.id(), entity.attribute_name(i)))
                    continue
                else: pass
            else:
                attr_name = attr.name()

                if attr_name == 'GlobalId': 
                    uuid_value = ifcopenshell.guid.split(ifcopenshell.guid.expand(attr_value))[1:-1]
                    uuid_uri = attrs['uuid']
                    ifc_id_uri = attrs['ifc-globalId']
                    g.add((instance_uri, uuid_uri, Literal(uuid_value, datatype = XSD.string)))
                    g.add((instance_uri, ifc_id_uri, Literal(attr_value, datatype = XSD.string)))
                    continue
                
                if attr_name not in attrs.keys(): continue
                
                attr_type = attr.type_of_attribute()

                #get object property uri
                property_uri = attrs[attr_name]

                if attr_type.as_named_type() or attr_type.as_simple_type():

                    if property_uri not in created_entities[instance_uri]:
                        #add property to entity dict
                        created_entities[instance_uri].append(property_uri)

                    attr_declaration = attr_type.declared_type()

                    if attr_declaration.as_type_declaration():
                        g.add((instance_uri, property_uri, Literal(attr_value, datatype=URIRef(type_maps[attr_type.declared_type().name()]))))  
                    
                    elif attr_declaration.as_entity():
                        if attr_value.is_a() in config_file.keys():
                            property_item_uri = create_entity(attr_value)
                            g.add((instance_uri, property_uri, property_item_uri))
                                                   

        # get the inverse attributes 
        inverse_attributes =  entity_schema.all_inverse_attributes()
        for inv_attr  in inverse_attributes:

            
            inverse_attr_label = inv_attr.name()

            if inverse_attr_label not in attrs.keys(): continue
            


            inv_attr_uri = attrs[inverse_attr_label]
            reference_entity= inv_attr.entity_reference()


            reference_entity_attrs = [item for item in reference_entity.all_attributes() if item.name() not in ['GlobalId','OwnerHistory', 'Name', 'Description', 'RelatedObjectsType', 'ActingRole', 'ConnectionGeometry', 'QuantityInProcess', 'SequenceType', 'TimeLag', 'UserDefinedSequenceType' ]]
            inverse_of_attr = inv_attr.attribute_reference()
            reference_entity_attr = None
                        
            if len(reference_entity_attrs) > 2: continue
            
            if len(reference_entity_attrs)==2:
                for ref_attr in reference_entity_attrs:
                    if inverse_of_attr.name() != ref_attr.name():
                        reference_entity_attr = ref_attr #this wont work well if the ref  entity has more than 2 attrs
            else: reference_entity_attr = reference_entity_attrs[0]            
                      
            relations = getattr(entity, inv_attr.name())
            
            if relations: 
                for relation in relations:
                    content = getattr(relation, reference_entity_attr.name())
                    if isinstance(content, tuple) or isinstance(content, list):
                        for item in content:
                            if item.is_a()[3:] not in config_file.keys(): continue
                            property_item_uri = create_entity(item)
                            g.add((instance_uri, inv_attr_uri, property_item_uri))
                    else:
                        if content.is_a()[3:] not in config_file.keys():  continue
                        property_item_uri = create_entity(content)
                        g.add((instance_uri, inv_attr_uri, property_item_uri))                  
    
    return instance_uri

## geometrical information TODO (still testing)

def create_geometry(entity, format,  output_path, output_name, file_size): #TODO other geometry formats
    go = output_path + output_name +"."+ format
    if hasattr(entity, 'Representation'):
        representation = entity.Representation
        geom_instance = INST['geom_'+ str(entity.id())]
        entity_instance = INST[entity.is_a()[3:]+ '_' + str(entity.id())]
        g.add((entity_instance, OMG.hasGeometry, geom_instance))
        g.add((geom_instance, RDF.type, GOM.MeshGeometry))
        g.add((geom_instance, GOM.hasFileSize, Literal(file_size, datatype=XSD.integer)))
        g.add((geom_instance, FOG['asIfc'], Literal(go, datatype = XSD.anyURI)))
        g.add((geom_instance, FOG['hasIfcId-guid'], Literal(entity.GlobalId, datatype = XSD.string)))

if not params['geometry-output']['output-path'].endswith('/'): params['geometry-output']['output-path'] = params['geometry-output']['output-path'] +  '/'

for entity in file:
    if entity.is_a()[3:] in config_file.keys():
        create_entity(entity)
        if params['geometry-output']['convert']: 
            create_geometry(entity, params['geometry-output']['output-format'], params['geometry-output']['output-path'], params['rdf-output']['output-name'],  file_size_bytes) 

#process geometry file TODO
geometry_file = file

#save geometry file
file.write(params['geometry-output']['output-path']+ params['rdf-output']['output-name']+"."+ params['geometry-output']['output-format'])

# Save rdf asset
g.serialize(destination= save_path + '.ttl', format ='turtle')