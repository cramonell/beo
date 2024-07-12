from ifcopenshell import ifcopenshell_wrapper
import json
from rdflib import Graph, Namespace, Literal, URIRef, BNode 
import datetime
import pathlib

script_dir = pathlib.Path(__file__).parent
config_path = (script_dir / 'config.json').resolve()
ontology_config_file = (script_dir / 'beo-config.json').resolve()

with open(config_path, 'r',encoding='utf-8') as fp:
    p =json.load(fp)
    save_folder = p['output-path']
    save_format = p['output-format']

with open(ontology_config_file, 'r',encoding='utf-8') as fp:
    config_file =json.load(fp)


# load the express IFC schema
schema_name = "IFC4X3_Add2"
schema = ifcopenshell_wrapper.schema_by_name(schema_name)

# Create a new graph
g = Graph()

#ontology ref specification
base_ref = "https://w3id.org/beo#"
ref = URIRef(base_ref)

# Create a namespaces for the ontology
BEO = Namespace(ref)
EXPRESS = Namespace('https://w3id.org/express#')
CC = Namespace('http://creativecommons.org/ns#')
DCE = Namespace("http://purl.org/dc/elements/1.1/")
VANN = Namespace("http://purl.org/vocab/vann/")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
SCHEMA = Namespace("https://schema.org/")

# Bind your custom prefix
g.bind("beo", BEO)
g.bind('rdf', RDF)
g.bind('rdfs', RDFS)
g.bind('owl', OWL)
g.bind('vann', VANN)
g.bind('xsd', XSD)
g.bind('express',EXPRESS)
g.bind('cc', CC)
g.bind('dce', DCE)
g.bind('schema', SCHEMA)

def is_supertype(entity, supertype:str):
    inheritance=[]

    while entity.supertype():
        inheritance.append(entity.supertype().name())
        entity=entity.supertype()

    for i in range(len(inheritance)):
        inheritance[i]=inheritance[i]
    
    if supertype in inheritance:
        return True
    else: return False

def get_suertypes(entity):
    inheritance=[]

    while entity.supertype():
        inheritance.append(entity.supertype().name())
        entity=entity.supertype()

    for i in range(len(inheritance)):
        inheritance[i]=inheritance[i]
    
    return inheritance

def untangle_named_type_declaration(attr_declared_type):
    last_declared_type = attr_declared_type.declared_type()
    if last_declared_type.declared_type().declared_type().as_named_type():
        untangle_named_type_declaration(last_declared_type.declared_type())
    else:
        return last_declared_type.declared_type().declared_type()

def unnest_select(select, items: list):
    for item in select.select_list():
        if not item.as_select_type():
            items.append(item)
        else: unnest_select(item, items)
    return items

def iterate_subtypes_inverse_attrs(entity, inverse_attributes):
    sup_inv_attrs =  [sup_inv_attr.name() for sup_inv_attr in entity.all_inverse_attributes()]
    for subtype in entity.subtypes():
        inverse_attributes[subtype.name()]=[inv_attr.name() for inv_attr in subtype.all_inverse_attributes() if inv_attr.name() not in sup_inv_attrs]
        if subtype.name()== 'IfcProduct': 
            inverse_attributes[subtype.name()]=[inv_attr.name() for inv_attr in subtype.all_inverse_attributes()]
        iterate_subtypes_inverse_attrs(subtype,inverse_attributes)

def add_named_type_attr(entity_name, attr_name, type_of_attr, optional):

    if type_of_attr.declared_type().as_entity() and type_of_attr.declared_type().name() not in  config_file.keys():
        return  False
    
    elif type_of_attr.declared_type().as_entity():
        #as object property
        g.add((BEO[attr_name], RDF.type,  OWL.ObjectProperty))
        #define domain
        g.add((BEO[attr_name], RDFS.domain,  BEO[entity_name[3:]]))
        #add range to the attribute class
        range_name = BEO[type_of_attr.declared_type().name()[3:]]
        g.add((BEO[attr_name], RDFS.range,  range_name))
    
    elif type_of_attr.declared_type().as_select_type():
        items = type_of_attr.declared_type().select_list()
        applied = False
        applieds = 0
        for item in items:
            if item.as_entity():
                if item.name() in config_file.keys(): applied = True
                if applied:
                    applieds += 1
                    #as object property
                    g.add((BEO[attr_name], RDF.type,  OWL.ObjectProperty))
                    #define domain
                    g.add((BEO[attr_name], RDFS.domain,  BEO[entity_name[3:]]))
                    #add range to the attribute class
                    range_name = BEO[item.name()[3:]]
                    g.add((BEO[attr_name], RDFS.range,  range_name))
                applied = False

            elif item.as_type_declaration():
                applied = True
                applied += 1
                #as datatype property
                g.add((BEO[attr_name], RDF.type,  OWL.DatatypeProperty))
                #define domain
                g.add((BEO[attr_name], RDFS.domain,  BEO[entity_name[3:]]))
                #range to the attribute class
                range_name = type_maps[item.name()[3:]]
                g.add((BEO[attr_name], RDFS.range,  range_name))
        if applieds == 0 : return False
        
    elif type_of_attr.declared_type().as_enumeration_type(): #create  collection
        #as data property
        g.add((BEO[attr_name], RDF.type,  OWL.DatatypeProperty))

         #define domain
        g.add((BEO[attr_name], RDFS.domain,  BEO[entity_name[3:]]))

        range_name = XSD.string
        
        #add range to the attribute class
        g.add((BEO[attr_name], RDFS.range, range_name))

    else:
        #as object property
        g.add((BEO[attr_name], RDF.type,  OWL.DatatypeProperty))
        
        #define domain
        g.add((BEO[attr_name], RDFS.domain,  BEO[entity_name[3:]]))
        
        #range to the attribute class
        range_name = type_maps[type_of_attr.declared_type().name()]
        g.add((BEO[attr_name], RDFS.range,  range_name))
    
    #define as functional property
    g.add((BEO[attr_name], RDF.type,  OWL.FunctionalProperty))
    
    return True


#add ontology header triples
g.add((ref, RDF.type, OWL.Ontology))
g.add((ref, DCE.creator, Literal('Carlos Ramonell Cazador (carlos.ramonell@upc.edu)')))
g.add((ref, DCE.date, Literal('2024/04/11')))
g.add((ref, DCE.description, Literal("OWL ontology to describe built elements in the built environment. It is based on the Product ontology descibed in IFC (Insutry Foundation Classes) schema.")))
g.add((ref, DCE.identifier, Literal('Built Element Ontology')))
g.add((ref, DCE.title, Literal('Built Element Ontology')))
g.add((ref, DCE.language, Literal('en')))
g.add((ref, DCE.abstract, Literal(f"This Ontology is automatically using the IFCExpress2BEO custom converter developed  by Carlos Ramonell (carlos.ramonell@upc.edu)")))
g.add((ref, VANN.preferredNamespaceUri, Literal(ref)))
g.add((ref, VANN.preferredNamespacePrefix, Literal('beo')))
g.add((ref, CC.license, Literal('http://creativecommons.org/licenses/by/3.0/')))
g.add((ref, OWL.versionIRI, ref))
g.add((ref, OWL.versionInfo, Literal('1.0')))

# anotation properties
g.add((DCE.creator, RDF.type, OWL.AnnotationProperty))
g.add((DCE.contributor, RDF.type, OWL.AnnotationProperty))
g.add((DCE.date, RDF.type, OWL.AnnotationProperty))
g.add((DCE.title, RDF.type, OWL.AnnotationProperty))
g.add((DCE.description, RDF.type, OWL.AnnotationProperty))
g.add((DCE.identifier, RDF.type, OWL.AnnotationProperty))
g.add((DCE.language, RDF.type, OWL.AnnotationProperty))


# create empty list to filter different types of declarations
simple_types = {}
named_types = {}
aggregation_types = []
enumerations = []
selects = []
entities = []
labels = {}

ignore_attrs =[    
            "Name",
            "OwnerHistory",
            "RefLatitude",
            "RefLongitude",
            "RefElevation",
            "ReferencedInStructures",
            "ContainedInStructure",
            "hasContext",
            "ObjectType",
            "UserDefinedOperationType",
            "UsageType",
            "GlobalId",
            "ObjectPlacement",
            "CompositionType",
            "OperationType",
            "ConstructionType",
            "AssemblyPlace",
            "UserDefinedPartitioningType",
            "PartitioningType"
        ]
type_maps = {}

#prepare entities and type maps
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

    elif declaration.as_entity(): #List entities to process them later
        entities.append(declaration)
    
sub_ontology_root = ['IfcBuiltElement', 'IfcElementAssembly', 'IfcElementComponent', 'IfcTransportElement'] # The Root class for the ontology

# Create entities
for entity  in entities:

    entity_name = entity.name()

    if entity_name[3:] not in config_file.keys(): continue

    # get root class data
    if entity_name in sub_ontology_root:
        supertype =  None
    else:
        supertype =  entity.supertype()
    attrs = entity.attributes()

    # get attributes abstract, derived anda list of the class subtypes to create the graph 
    abstract = entity.is_abstract()
    derived =entity.derived()
    subtypes = [subtype.name() for subtype in entity.subtypes()]

    # get descriptions and labels
    labels = []
    descriptions = []
    for key in config_file[entity_name[3:]].keys():
        if key.startswith('label'):
            label = config_file[entity_name[3:]][key]
            label_key = key.split('-')
            labels.append({'label':label,'lang':label_key[1]})
        elif key.startswith('description'):
            description = config_file[entity_name[3:]][key]
            description_key = key.split('-')
            descriptions.append({'description':description,'lang':description_key[1]})
    
    # Add the class to the graph
    g.add((BEO[entity_name[3:]], RDF.type, OWL.Class))

    # Add the labels and descriptions
    for label_object in labels:
        g.add((BEO[entity_name[3:]], RDFS.label, Literal(label_object['label'], lang=label_object['lang'])))
    for description_object in descriptions:
        g.add((BEO[entity_name[3:]], RDFS.comment, Literal(description_object['description'], lang=description_object['lang'])))

    
    # Create dijsoint condition with all classes that share supertype
    if supertype: 
        g.add((BEO[entity_name[3:]], RDFS.subClassOf, BEO[supertype.name()[3:]]))
        disjoint = [subtype.name() for subtype in supertype.subtypes()]
        for disjoint_entity in disjoint: # ONE OF restriction in express applied to the subclasses of the superclass of the processed entity.
            if disjoint_entity != entity_name and disjoint_entity in config_file.keys(): g.add((BEO[entity_name[3:]], OWL.disjointWith, BEO[disjoint_entity[3:]]))

    # If it is an abstract supertype declare the class a subclass of the union of its subclasses 
    if abstract: 
        collection = []
        abstract_node = BNode()
        collection_node =BNode()
        item1 = collection_node
        item2 = BNode()
        
        for i  in range(len(subtypes)):
            if subtypes[i] in config_file.keys():
                collection.append(subtypes[i])
        if len(collection) == 0: pass
        
        elif len(collection) == 1:            
            g.add((BEO[entity_name[3:]], RDFS.subClassOf, BEO[collection[0][3:]]))
        
        elif len(collection)> 1:
            for i in range(len(collection)):
                g.add((item1, RDF.first, BEO[collection[i][3:]]))
                g.add((item1, RDF.rest, item2))
                item1 = item2
                if i == len(collection)-2: item2 = RDF.nil
                else: item2 = BNode()

            g.add((abstract_node, RDF.type, OWL.Class))

            g.add((abstract_node, OWL.unionOf, collection_node))
            
            g.add((BEO[entity_name[3:]], RDFS.subClassOf, abstract_node))
    
    # Add attributes
    for attr in attrs:
        
        attr_label = attr.name()
        
        #if the attribute label is  already in the attr_ignore list, skip it.
        if attr_label in ignore_attrs:
            continue

        attr_name = attr_label[0].lower() + attr_label[1:]
        type_of_attr = attr.type_of_attribute()
        optional = attr.optional()
        
        #If the attribute label is PredefinedType and leads to an Enum, extend the entity class creating as subclasses  the  enum items
        if attr_label == 'PredefinedType':
            if attr.type_of_attribute().declared_type().as_enumeration_type():
                items = [item for item in attr.type_of_attribute().declared_type().enumeration_items() if item not in ['USERDEFINED', 'NOTDEFINED']]
                
                for item in items:
                    
                    if item in config_file[entity_name[3:]]['enum'].keys():
                        enumerations.append(item)
                        #get all teh labels and descriptions
                        labels = []
                        descriptions = []

                        for key in config_file[entity_name[3:]]['enum'][item].keys():
                            if key.startswith('label'):
                                label = config_file[entity_name[3:]]['enum'][item][key]
                                label_key = key.split('-')
                                labels.append({'label':label,'lang':label_key[1]})
                            elif key.startswith('description'):
                                description = config_file[entity_name[3:]]['enum'][item][key]
                                description_key = key.split('-')
                                descriptions.append({'description':description,'lang':description_key[1]})

                        label_en = config_file[entity_name[3:]]['enum'][item]['label-en']
                        item_name = label_en.replace(' ', '')

                        g.add((BEO[item_name], RDF.type, OWL.Class))
                        g.add((BEO[item_name], RDFS.subClassOf, BEO[entity_name[3:]]))

                        for label_object in labels:
                            g.add((BEO[item_name], RDFS.label, Literal(label_object['label'], lang=label_object['lang'])))
                        for description_object in descriptions:
                            g.add((BEO[item_name], RDFS.comment, Literal(description_object['description'], lang=description_object['lang'])))

            continue

        if type_of_attr.as_named_type():
            if not add_named_type_attr(entity_name, attr_name, type_of_attr, optional): continue
        
        # Add attr label to the graph
        g.add((BEO[attr_name], RDFS.label,  Literal(attr_label)))

for root in sub_ontology_root:
    g.add((BEO[root[3:]], RDFS.subClassOf, SCHEMA.Product))

date = datetime.datetime.now()

path = save_folder + 'beo_' + datetime.datetime.today().strftime('%Y%m%d')

g.serialize(destination= path + '.' + save_format, format =save_format)



