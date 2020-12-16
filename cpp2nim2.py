#!/usr/bin/env python
""" Usage: call with <filename> <typename>
python cpp2nim.py "/usr/include/opencascade/gp_*.hxx" occt
python cpp2nim.py /usr/include/osg/Geode geode

>>> import clang.cindex
>>> index = clang.cindex.Index.create()
>>> tu = index.parse("/usr/include/opencascade/gp_Pnt.hxx", ['-x', 'c++',  "-I/usr/include/opencascade"], None, clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)

clang -Xclang -ast-dump=json -x c++ -I/usr/include/osg -fsyntax-only /usr/include/osg/Geode  > geode.json

clang -Xclang -ast-dump -fno-diagnostics-color miniz.c

TODO: si sale Clase & significa que hay que usar byref y en caso contrario: bycopy

TODO: enum

From:
enum BRepPrim_Direction
{
BRepPrim_XMin,
BRepPrim_XMax,
BRepPrim_YMin,
BRepPrim_YMax,
BRepPrim_ZMin,
BRepPrim_ZMax
};


To:
type
  BRepPrim_Direction* {.size: sizeof(cint), importcpp: "BRepPrim_Direction",
                       header: "BRepPrim_Direction.hxx".} = enum
    BRepPrim_XMin, BRepPrim_XMax, BRepPrim_YMin, BRepPrim_YMax, BRepPrim_ZMin,
    BRepPrim_ZMax

-----
TODO:
El tipo de Geode debería ser:
C++:
   class Geode : public Group

type
  Geode* {.importcpp: "osg::Geode", header: "Geode", bycopy.} = object of Group

pero yo:
  Geode* {.header: "Geode", importcpp: "Geode", byref.} = object
-----
TODO:
C++:
        /** Copy constructor using CopyOp to manage deep vs shallow copy.*/
        Geode(const Geode&,const CopyOp& copyop=CopyOp::SHALLOW_COPY);
C2NIM:
  proc constructGeode*(a1: Geode; copyop: CopyOp = SHALLOW_COPY): Geode {.constructor,
      importcpp: "osg::Geode(@)", header: "Geode".}

CPP2NIM:
  proc constructor_Geode*(Geode, copyop: Copyop): Geode {.constructor,importcpp: "Geode(@)".}
    ## Copy constructor using CopyOp to manage deep vs shallow copy.

TODO:
C++:
template<class T> bool addDrawable( const ref_ptr<T>& drawable ) { return addDrawable(drawable.get()); }

C2NIM:
proc addDrawable*[T](this: var Geode; drawable: ref_ptr[T]): bool {.
    importcpp: "addDrawable", header: "Geode".}

CPP2NIM:
nothing

TODO: 
C++:
        virtual bool removeDrawables(unsigned int i,unsigned int numDrawablesToRemove=1);
C2NIM:
  proc removeDrawables*(this: var Geode; i: cuint; numDrawablesToRemove: cuint = 1): bool {.
    importcpp: "removeDrawables", header: "Geode".}

CPP2NIM:
   proc removeDrawables*(this: var Geode, i: cuint, numDrawablesToRemove: cuint): bool  {.importcpp: "removeDrawables".}


TODO:
C++:
        template<class T, class R> bool replaceDrawable( const ref_ptr<T>& origDraw, const ref_ptr<R>& newDraw ) { return replaceDrawable(origDraw.get(), newDraw.get()); }
C2NIM:
proc replaceDrawable*[T; R](this: var Geode; origDraw: ref_ptr[T]; newDraw: ref_ptr[R]): bool {.
    importcpp: "replaceDrawable", header: "Geode".}

CPP2NIM:


"""

import sys
import clang.cindex
import string
import os
import glob
import textwrap
import re
from pprint import pprint
#import oyaml as yaml
#import networkx as nx

my_dict = {}

#function_calls = []             # List of AST node objects that are function calls
function_declarations = []      # List of AST node objects that are fucntion declarations


# Traverse the AST tree
def get_nodes(node,depth=0):
    yield (depth, node)
    for child in node.get_children():
        yield from get_nodes(child, depth = depth+1)


def get_nim_type( c_type ):
    c_type = c_type.strip()

    isVar = True
    if c_type[0:5] == "const":
        c_type = c_type[5:].strip()
        isVar = False

    if c_type[-1] != "&":
        isVar = False
    else:
        c_type = c_type[:-1]

    c_type = c_type.strip()

    if c_type in ["void *"]:
        return "pointer"
    if c_type in ["long"]:
        return "clong"
    if c_type in ["unsigned long"]:
        return "culong"
    if c_type in ["short"]:
        return "cshort"
    if c_type in ["int"]:
        return "cint"
    if c_type in ["size_t"]:
        return "csize_t"    
    if c_type in ["long long"]:
        return "clonglong"              
    #if c_type in ["signed", "unsigned"]:
    #    return "cint"
    if c_type in ["long double"]:
        return "clongdouble" 
    if c_type in ["float"]:
        return "cfloat"        
    if c_type in ["double"]:
        return "cdouble"
    if c_type in ["char *"]:
        return "cstring"
    if c_type in ["char"]:
        return "cchar"
    if c_type in ["signed char"]:
        return "cschar"
    if c_type in ["unsigned char"]:
        return "cuchar"
    if c_type in ["unsigned short"]:
        return "cushort"
    if c_type in ["unsigned int"]:
        return "cuint"
    if c_type in ["unsigned long long"]:
        return "culonglong"
    if c_type in ["char**"]:
        return "cstringArray"

    if isVar:
        c_type = f"var {c_type}"

    # xxxx::yyyy<zzzzz>
    if "::" in c_type:
        kernel = re.compile("([^<]+)[<]*([^>]*)[>]*")
        _a, _b = kernel.findall(c_type)[0]
        _tmp = _a.split("::")[-1]
        _tmp = _tmp.capitalize()

        my_dict[_tmp] = f'{_tmp}* {{.importcpp: "{_a}", header: "<map>".}} [K] = object'
        if _tmp[-1] == "*":
            _tmp = f"ptr {_tmp[:-1]}"
        if _b != "":
            _b = f"[{_b}]"
        return f"{_tmp}{_b}"

    if "<" in c_type and ">" in c_type:
        c_type = c_type.replace("<", "[")
        c_type = c_type.replace(">", "]")

    return c_type


def clean(txt):
    txt = txt.replace("const", "")
    txt = txt.strip()
    if txt[-2:] == " &":
        txt = txt[:-2]
    return txt
#----------- EXPORTING  

def export_params(params):
    _params = ""
    n = 0
    for p in  params:
        if n > 0:
            _params += ", "
        if p[0]:
            _params += clean(p[0]) + ": "
        _type = get_nim_type(p[1])
        _params += _type
        n += 1
    return _params 


def get_comment(data):
    _tmp = ""
    _comment = data["comment"]
    if  _comment != None:
        _comment = textwrap.fill(_comment, width=70).split("\n")
        for i in _comment:
            _tmp += f"  ## {i}\n"
    return _tmp

def get_constructor(data):
    _params = export_params(data["params"])   
    _tmp = ""
    if _params != "":
        _tmp = "(@)"
    _tmp = f'proc construct{data["name"]}*({_params}): {data["class_name"]} {{.constructor,importcpp: "{data["name"]}{_tmp}".}}\n'
    _tmp += get_comment(data)  + "\n"
    return _tmp    

def get_method(data):
    _params = export_params(data["params"])
    if _params != "":
        _params = ", " + _params

    _classname = data["class_name"]
    if not data["const_method"]:
        _classname = f"var {_classname}"

    _params = f'this: {_classname}' + _params
    
    _return = ""
    if data["result"] not in ["void", "void *"]:
        _result = data["result"].strip()
        if _result.startswith("const "):
            _result = _result[6:]
        if _result[-1] == "&":
            _result = _result[:-1].strip()
        _result = get_nim_type( _result )
        _return = f': {_result}'

    _methodName = data["name"]
    _methodName = _methodName[0].lower() + _methodName[1:]
    _importName = data["name"]
    # Operator case
    if _importName.startswith("`") and _importName.endswith("`"):
        _importName = _importName[1:-1]
        _importName = f"# {_importName} #"
    
    _templParams = ""
    if "templParams" in data:
        if len(data["templParams"]) > 0:
            _templParams = "[" + ";".join( data["templParams"] ) + "]"
            pprint(data)
        #print(_templParams)

    _tmp = f'proc {_methodName}*{_templParams}({_params}){_return}  {{.importcpp: "{_importName}".}}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp



def get_typedef(data, include = None):   # TODO: añadir opción si no está referenciado, comentar
    #for i in data:
        #if i["name"] in _types:
    _type = get_nim_type( data["underlying"] )
    _include = ""
    if include != None:
        _include = f'header: "{include}", '
    return f'  {data["name"]}* {{.{_include}importcpp: "{data["name"]}".}} = {_type}\n'
    #_data[_file]["typedefs"].append((i["name"], _type))

def get_class(data, include = None, byref = True):
    #pprint(data)
    _name = data["name"]
    _include = ""
    if include != None:
        _include = f'header: "{include}", '
    _byref = ", byref" 
    if not byref:
        _byref = ", bycopy"
    _tmp = f'  {_name}* {{.{_include}importcpp: "{_name}"{_byref}.}} = object\n'
    _tmp += get_comment(data) + "\n"
    return _tmp    


def export_per_file(data, files = [], output= "occt", filter=None):
    _fname = os.path.join(output,output) + ".nim"
    _fp1 = open(_fname, "a+")

    _newfiles = []
    filtered_files = [i for i in files if i.startswith(filter)]
    #print(files)
    for _file in filtered_files:
        _typedefs     = []
        _constructors = []
        _methods      = []
        _classes      = []
        for item in data:
            if _file in item[0]:
                _tmpFile = _file.split(filter)[1]
                if item[1] == "constructor":
                    _constructors.append(get_constructor(item[2]))
                    #print(item2[2])
                    #_classes.append(get_class(item[2], _tmpFile))
                elif item[1] in ["method", "template"]:
                    _methods.append(get_method(item[2]))
                    #_classes.append(get_class(item[2], _tmpFile))
                elif item[1] == "typedef":
                    _typedefs.append( get_typedef(item[2], _tmpFile))
                elif item[1] == "class":
                    _classes.append(get_class(item[2], _tmpFile))
                
        _fname = ""
        _popfile = None
        if filter != None:
            _fname = _file.split(filter)[1]
            _popfile = _fname
        _fname = os.path.splitext(_fname)[0]
        _nimname = _fname + ".nim"
        _newfiles.append( _nimname)        
        _fname = os.path.join(output, _nimname)
        #print(_methods)
        if len(_typedefs) > 0 or len(_classes) > 0:
            #_fp1.write(f'{{.push header: "{_popfile}".}}\n')
            #_fp1.write("type\n")
            for _i in _typedefs:
                _fp1.write(_i)
            for _i in _classes:
                _fp1.write(_i)                
            #_fp1.write(f'{{.pop.}} # header: "{_popfile}\n')

        if len(_constructors) > 1 or len(_methods) > 1:
            #print("METHODS")
            _fp = open(_fname, "w")
            _fp.write(f'{{.push header: "{_popfile}".}}\n')        
            _fp.write("\n\n# Constructors and methods\n")
            for _i in _constructors:
                _fp.write(_i)
            for _i in _methods:
                _fp.write(_i)        
            _fp.write(f'{{.pop.}} # header: "{_popfile}\n')
            _fp.close()

    _fp1.close()



def get_root(_blob):
    # Case where a specific file is given (no blob)
    if "*" not in _blob and "?" not in _blob:
        _tmp = _blob.split("/")
        _out = ""
        for i in _tmp[:-1]:
            _out += i + "/"
        return _out
    # Blob case
    _tmp = _blob.split("/")
    _out = ""
    for i in _tmp:
        if "*" not in i:
            _out += i + "/"
    return _out


if __name__ == '__main__':
    _folder = sys.argv[1]
    _dest = sys.argv[2]
    _path = os.getcwd()
    _destination_folder = os.path.join(_path, _dest)
    try:
        os.mkdir(_destination_folder)
    except:
        pass

    _root = get_root(_folder)    
    _files = glob.glob(_folder, recursive = True)

    print("Root folder: ", _root)

    #for root, dirs, files in os.walk(_folder): 
    _fname = os.path.join(_dest,_dest) + ".nim"
    _fp1 = open(_fname, "w")
    _fp1.write('{.passL: "-losg -losgSim -losgAnimation -losgTerrain -losgDB -losgText -losgFX -losgUI -losgGA -losgUtil -losgManipulator -losgViewer -losgParticle -losgVolume -losgPresentation -losgWidget -losgShadow", passC:"-I/usr/include/osg" .}\n\n')
    _fp1.write("type\n")            
    _fp1.close()    


    _nTotal = len(_files)
    _n = 1
    for include_file in _files:
        print(f"Parsing ({_n}/{_nTotal}): {include_file}")
        _n += 1

        index = clang.cindex.Index.create()
        args = ['-x', 'c++',  f"-I{_folder}"]  # "-Wall", '-std=c++11', '-D__CODE_GENERATOR__'
        #opts = TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES # a bitwise or of TranslationUnit.PARSE_XXX flags.
        opts = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        #fname = os.path.join(_root,include_file)
        tu = index.parse(include_file, args, None, opts)
   
        _all = []
        #_constructors = []
        _methods = []
        _typedefs = []
        for depth,node in get_nodes( tu.cursor, depth=0 ):  # Traverses the whole tree
            _node = {}
            # Operator
            if node.kind == clang.cindex.CursorKind.OVERLOADED_DECL_REF:
                pass


            # Constructors
            if node.kind == clang.cindex.CursorKind.CONSTRUCTOR:
                _data = { "name" : node.spelling,
                          "class_name": node.semantic_parent.spelling,
                          "comment": node.brief_comment }

                _params = []
                for i in node.get_children():
                    if i.kind == clang.cindex.CursorKind.PARM_DECL:
                        _paramName = i.displayname
                        _params.append((i.displayname, i.type.spelling))
                _data["params"] = _params
                
                _file = node.location.file.name
                _all.append(( _file, "constructor", _data ))
                                    

            # Methods
            if node.kind == clang.cindex.CursorKind.CXX_METHOD:
                _name = node.spelling
                if _name.startswith("operator"):
                    _tmp = _name[8:]
                    if re.match("[+-=*\^/]+", "+-+=*^"):
                        _name = f'`{_tmp}`'
                
                _data = {"name" : _name}
                _data["result"] = node.result_type.spelling
                _data["class_name"] = node.semantic_parent.spelling
                _data["const_method"] = node.is_const_method()

                _params = []
                for i in node.get_children():
                    if i.kind == clang.cindex.CursorKind.PARM_DECL:
                        _paramName = i.displayname
                        _params.append((i.displayname, i.type.spelling))
                _data["params"] = _params
                _data["comment"] = node.brief_comment
                _all.append(( node.location.file.name, "method", _data ))

            # Classes
            if node.kind == clang.cindex.CursorKind.CLASS_DECL and node.is_definition():
            #if node.spelling == "gp_Trsf2d":
                _data = { "name" : node.spelling,
                          "comment": node.brief_comment }
                _all.append(( node.location.file.name, "class", _data ))

            # Types
            # Methods
            if node.kind == clang.cindex.CursorKind.TYPEDEF_DECL:
                _data = { "name" : node.displayname,
                          "underlying": node.underlying_typedef_type.spelling }          
                _all.append(( node.location.file.name, "typedef", _data ))


            # CursorKind.CXX_METHOD CursorKind.FUNCTION_TEMPLATE CursorKind.OVERLOADED_DECL_REF
            if node.kind == clang.cindex.CursorKind.FUNCTION_TEMPLATE:
                _data = { "name" : node.spelling,
                          "comment": node.brief_comment }

                _data = {"name" : _name}
                _data["result"] = node.result_type.spelling
                _data["class_name"] = node.semantic_parent.spelling
                _data["const_method"] = node.is_const_method()
                _data["comment"] = node.brief_comment                                   
                _params = []
                _templParams = []
                for i in node.get_children():
                    if i.kind == clang.cindex.CursorKind.PARM_DECL:
                        _paramName = i.displayname
                        _params.append((i.displayname, i.type.spelling))
                    elif i.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
                        if node.spelling == "replaceDrawable": 
                            _templParams.append(i.displayname)
                
                _data["params"] = _params
                _data["templParams"] = _templParams                

                # Parámetros
                #if node.spelling == "replaceDrawable": 
                #    pprint(_data)
                _all.append(( node.location.file.name, "template", _data ))

        # Only consider data associated to the file itself
        _all = [i for i in _all if i[0] == include_file]

        export_per_file( _all, files = [include_file], 
                         output=_dest,
                         filter=_root)

    _fp1 = open(_fname, "a+")
    #_fp1.write("\n\n")
    for k,v in my_dict.items():
        _fp1.write(f"  {v}\n\n")

    for _file in _files:
        _fname = _file.split(_root)[1]
        _fname = os.path.splitext(_fname)[0]
        _fp1.write(f'include "{_fname}.nim"\n')
    _fp1.close()            
