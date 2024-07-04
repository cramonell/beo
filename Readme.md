BEO stands for [Built Element Ontology](https://cramonell.github.io/beo/actual/index-en.html). It is an ontology inspired by  the entities of the [Industry Foundation Classes](https://ifc43-docs.standards.buildingsmart.org/) schema(IFC) that represent built elements and spatial configurations in the built environment. In this repository you will find a schema converter from IFC (express) to BEO (owl) . 


## How to Use
1. **Installation**:
   - Install python in your machine
   - clone this repository
   - Install requirements : [ifcopenshell](https://ifcopenshell.org/), [rdflib](https://rdflib.readthedocs.io/en/stable/index.html)

2. **Usage**:
   - Run the script  either from the command line or from your prefered code editor. Each converter use a config.json file (explained below).
   - The ontology-config.json file contains the mapping between the IFC entities and the BEO entities and it is the base for both converters.

3. **Configuration BEO generator ([beo-gen](https://github.com/cramonell/beo/tree/main/beo-gen))**:
   - *output-path*: path were the output file will be saved
   - *output-format*: file format (ttl, nt, rdf/xml ...)

4. **License**:
   - This project is licensed under the GNU General Public License (GNU GPL). You can find the full text of the license in the LICENSE.txt file.



