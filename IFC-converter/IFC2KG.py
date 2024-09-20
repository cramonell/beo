import ifcopenshell
import ifcopenshell.geom
from rdflib import Graph, Namespace, Literal, URIRef
import json
import pathlib
import os

script_dir = pathlib.Path(__file__).parent
config_path = (script_dir / 'config.json').resolve()
ontology_config_file = (script_dir / 'conversion-map.json').resolve()

### PARAMETERS
with open(config_path, 'r',encoding='utf-8') as fp:
    params =json.load(fp)

with open(ontology_config_file, 'r',encoding='utf-8') as fp:
    config_file =json.load(fp)

# IFC file path
file_path = params['ifc-file-path']
if params['rdf-output']['output-name']: asset_name = params['rdf-output']['output-name']
else: asset_name = file_path.split('/')[-1].split('.')[0]

# load IFC file
file = ifcopenshell.open(file_path)
file_info = os.stat(file_path)
file_size_bytes = file_info.st_size

# urls
if params['rdf-output']['base-url'].endswith('/'): asset_base_ref = params['rdf-output']['base-url'] 
else: asset_base_ref = params['rdf-output']['base-url'] + '/'
asset_ref =  URIRef(asset_base_ref)
beo_ref =  URIRef("https://w3id.org/beo#")

if params['rdf-output']['output-path'].endswith('/'): save_path = params['rdf-output']['output-path'] + asset_name
else: save_path = params['rdf-output']['output-path'] + '/' + asset_name

### Load IFC schema (EXPRESS)
schema_name = str(file.schema)
schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(file.schema)

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
BOT = Namespace("https://w3id.org/bot#")
BROT =Namespace("https://w3id.org/brot#")
BRCOMP =Namespace("https://w3id.org/brcomp#")
BRIDGE =Namespace("https://w3id.org/bridge#")
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
g.bind("brot", BROT)
g.bind("bridge", BRCOMP)
g.bind("brcomp", BRIDGE)
g.bind("bot", BOT)
g.bind(params['rdf-output']['url-prefix'], INST)
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

#get aggregations
aggr = {}
aggregations = file.by_type('IfcRelAggregates')
for agg in aggregations:
    relating_object = agg.RelatingObject
    relating_object_name = relating_object.is_a()
    relating_instance_name = relating_object_name[3:] + '_' + str(relating_object.id())
    relating_instance = INST[relating_instance_name]
    aggr[relating_instance_name] = []
    for related_object in agg.RelatedObjects:
        related_object_name = related_object.is_a()
        related_instance_name = related_object_name[3:] + '_' + str(related_object.id())
        related_instance = INST[related_instance_name]
        
        if not relating_object.is_a('IfcSpatialElement'): continue
        
        elif relating_object.is_a('IfcSpatialElement') and related_object.is_a('IfcFacility') :
            relation = BOT.hasBuilding
        
        elif relating_object.is_a('IfcSpatialElement') and related_object.is_a('IfcSpace') :
            relation = BOT.hasSpace
        
        elif relating_object.is_a('IfcBuilding') and related_object.is_a('IfcBuildingStorey'):
            relation = BOT.hasStorey
        
        else: relation = BOT.ContainsZone

        g.add((relating_instance, relation, related_instance))



## non-geometrical information

def create_entity(entity)-> URIRef:

    # get the  IFC definition of the entity
    entity_schema = schema.declaration_by_name(entity.is_a())

    entity_name = entity_schema.name()

    instance_name = entity_name[3:] + '_' + str(entity.id())

    entity_uris = [URIRef(url) for url in config_file[entity_name]['class']]
    instance_uri = INST[instance_name]

    info = entity.get_info()
    if 'PredefinedType' in info.keys() and info['PredefinedType'] in config_file[entity_name]['enum'].keys() :
        entity_uris = [URIRef(url) for url in config_file[entity_name]['enum'][info['PredefinedType']]]


    if instance_uri not in created_entities.keys(): 
        created_entities[instance_uri] = []

        #create instance
        for entity_uri in entity_uris:
            g.add((instance_uri, RDF.type, entity_uri))

        #create instance attributes
        attr_count = entity_schema.attribute_count()

        attrs = config_file[entity_name]['attrs']
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
                
                if attr_name not in attrs.keys(): continue
                
                attr_type = attr.type_of_attribute()

                #get object property uri
                property_uri = URIRef(attrs[attr_name])

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

        inv_attrs = config_file[entity_name]['inv_attrs']
        for inv_attr  in inverse_attributes:
           
            inverse_attr_label = inv_attr.name()

            if inverse_attr_label not in inv_attrs.keys(): continue
            inv_attr_uri = URIRef(inv_attrs[inverse_attr_label])
            reference_entity= inv_attr.entity_reference()

            reference_entity_attrs = [item for item in reference_entity.all_attributes() if item.name() not in ['GlobalId','OwnerHistory', 'Name', 'Description', 'RelatedObjectsType', 'ActingRole', 'ConnectionGeometry', 'QuantityInProcess', 'SequenceType', 'TimeLag', 'UserDefinedSequenceType' ]]
            inverse_of_attr = inv_attr.attribute_reference()
            reference_entity_attr = None
                        
            if len(reference_entity_attrs) > 2: continue
            
            if len(reference_entity_attrs) == 2:
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
                            if item.is_a() not in config_file.keys(): continue
                            property_item_uri = create_entity(item)
                            g.add((instance_uri, inv_attr_uri, property_item_uri))
                    else:
                        if content.is_a() not in config_file.keys():  continue
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
    if entity.is_a() in config_file.keys():
        create_entity(entity)
        if params['geometry-output']['convert']: 
            create_geometry(entity, params['geometry-output']['output-format'], params['geometry-output']['output-path'], params['rdf-output']['output-name'],  file_size_bytes) 


#process geometry file TODO
geometry_file = file

#save geometry file
file.write(params['geometry-output']['output-path']+ params['rdf-output']['output-name']+"."+ params['geometry-output']['output-format'])

# Save rdf asset
g.serialize(destination= save_path + '.ttl', format ='turtle')