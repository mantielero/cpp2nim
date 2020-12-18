#!/usr/bin/env python
""" Usage: call with <filename> <typename>
python cpp2nim.py "/usr/include/opencascade/gp_*.hxx" occt
python cpp2nim.py /usr/include/osg/Geode geode

python cpp2nim.py "/usr/include/osg/**/*" osg
python cpp2nim.py "/usr/include/osgViewer/**/*" osgViewer
>>> import clang.cindex
>>> index = clang.cindex.Index.create()
>>> tu = index.parse("/usr/include/opencascade/gp_Pnt.hxx", ['-x', 'c++',  "-I/usr/include/opencascade"], None, clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)

clang -Xclang -ast-dump=json -x c++ -I/usr/include/osg -fsyntax-only /usr/include/osg/Geode  > geode.json

clang -Xclang -ast-dump -fno-diagnostics-color miniz.c
c2nim --cpp --header --out:gp_Pnt.nim /usr/include/opencascade/gp_Pnt.hxx

-----
TODO: si sale Clase & significa que hay que usar byref y en caso contrario: bycopy


-----
TODO:
C2NIM:
importcpp: "osg::Geode(@)"
YO:
Geode(@)

-----
TODO: https://nim-lang.org/docs/tut2.html#object-oriented-programming-inheritance
Definición de tipos. Si usamos "object of <something>", en algún momento 
habrá que hacer un "object of RootObj". También hay que tener claro si usamos:
"ref object of RootObj"

"""

import sys
import clang.cindex
import string
import os
import glob
import textwrap
import re
from pprint import pprint
from pathlib import Path
import collections


my_dict = { "const" : [], 
            "type": {}, 
            "typedefs": [], 
            "class": [], 
            "enums": []}

#function_calls = []             # List of AST node objects that are function calls
function_declarations = []      # List of AST node objects that are fucntion declarations


def print_line(node, field, spc, ident= 0):
    try:
        param = getattr(node, field)
        #print("------->", type(param))
        if callable(param):
            param = param()
        print(f"{spc}{field}: {param}")
        if isinstance( param, clang.cindex.Cursor):
            pp(_tmp, ident+ 4)
        elif isinstance(param, clang.cindex.Type):
            pptype(param, ident+4)

        elif hasattr(param,'__iter__'):#isinstance(param, collections.Iterable):
            pass
            #print(f"{spc}>>CHILDREN START:")
            #for i in param:
            #    pp(i, ident+4)
            #print(f"{spc}>>CHILDREN END:")                
    except:
        #print(f"{spc}{field}:  raises an exception!")    
        pass

def pptype(t, ident = 0):
    spc = " " * ident
    print(f"{spc}kind: ", node.kind) 
    print(f"{spc}spelling: ", node.spelling)    
    for i in dir(t):
        if not i.startswith("_") and i not in ["kind", "spelling"]:
            print_line(node, i, spc, ident)

def pp(node, ident = 0):
    """Pretty printer to inspect the nodes"""
    spc = " " * ident
    if ident == 0:
        print("======= TOP =======")
    else:
        print(f"{spc}------")
    print(f"{spc}kind: {node.kind}") 
    print(f"{spc}spelling: {node.spelling}" )
    for i in dir(node):
        if i not in ["kind", "spelling"] and not i.startswith("_"):
            print_line(node, i, spc, ident)   
    if ident == 0:
        print("======= BOTTOM =======")    
    else:
        print(f"{spc}------")

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

    # xxxx::yyyy<zzzzz> TODO: MODIFY <map>, [K]
    if "::" in c_type:
        kernel = re.compile("([^<]+)[<]*([^>]*)[>]*")
        _a, _b = kernel.findall(c_type)[0]
        _tmp = _a.split("::")[-1]
        _tmp = _tmp.capitalize()

        my_dict["type"][_tmp] = "#" + f'{_tmp}* {{.importcpp: "{_a}", header: "<map>".}} [K] = object'
        if _tmp[-1] == "*":
            _tmp = f"ptr {_tmp[:-1]}"
        
        if _b != "":
            # There may be several types
            _b = _b.split(", ")
            _b = [get_nim_type(_i) for _i in _b]
            for idx in range(len(_b)):
                if _b[idx][-1] == "*":
                    _b[idx]  = f"ptr {_b[idx][:-1].strip()}"
            _b = ",".join(_b)
            _b = f"[{_b}]"
        return f"{_tmp}{_b}"

    if "<" in c_type and ">" in c_type:
        c_type = c_type.replace("<", "[")
        c_type = c_type.replace(">", "]")

    if c_type[-1] == "*":
        c_type = f"ptr {c_type[:-1].strip()}"
    return c_type


NIM_KEYWORDS = ["addr", "and", "as", "asm", "bind", "block", "break",
                "case", "cast", "concept", "const", "continue", "converter",
                "defer", "discard", "distinct", "div", "do", "elif", "else",
                "end", "enum", "except", "export", "finally", "for", "from",
                "func", "if", "import", "in", "include", "interface", "is",
                "isnot", "iterator", "let", "macro", "method", "mixin", "mod",
                "nil", "not", "notin", "object", "of", "or", "out", "proc", "ptr",
                "raise", "ref", "return", "shl", "shr", "static", "template",
                "try", "tuple", "type", "using", "var", "when", "while", "xor",
                "yield"]

def clean(txt):
    txt = txt.replace("const", "")
    txt = txt.strip()
    if txt[-2:] == " &":
        txt = txt[:-2]
    if txt in NIM_KEYWORDS:
        txt = f"`{txt}`"
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
        if len(p) > 2:
            if p[2] != None:
                _type += f" = {p[2]}"

        _params += _type
        n += 1
    return _params 


def get_comment(data, n = 4):
    spc = " " * n
    _tmp = ""
    _comment = data["comment"]
    if  _comment != None:
        _comment = textwrap.fill(_comment, width=70).split("\n")
        for i in _comment:
            _tmp += f"{spc}## {i}\n"
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

    _tmp = f'proc {_methodName}*{_templParams}({_params}){_return}  {{.importcpp: "{_importName}".}}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp



def get_typedef(data, include = None):   # TODO: añadir opción si no está referenciado, comentar
    _type = get_nim_type( data["underlying"] )
    _include = ""
    if include != None:
        _include = f'header: "{include}", '

    if data["is_function_proto"]:
        # ActiveTextureProc* = proc (texture: GLenum)
        _return = ""
        if data["result"] not in ["void", "void *"]:
            _result = data["result"].strip()
            if _result.startswith("const "):
                _result = _result[6:]
            if _result[-1] == "&":
                _result = _result[:-1].strip()
            _result = get_nim_type( _result )
            _return = f': {_result}'        
        _params = export_params(data["params"])
        #if _params != "":
        #    _params = ", ".join(_params)
        
        _tmp = f"proc ({_params}){_return}"
        return f'  {data["name"]}* {{.{_include}importcpp: "{data["name"]}".}} = {_tmp}\n'
    else:
        return f'  {data["name"]}* {{.{_include}importcpp: "{data["name"]}".}} = {_type}\n'
    #_data[_file]["typedefs"].append((i["name"], _type))

def get_class(data, include = None, byref = True):
    _name = data["name"]
    _include = ""
    if include != None:
        _include = f'header: "{include}", '
    _byref = ", byref" 
    if not byref:
        _byref = ", bycopy"
    _inheritance = ""
    if len(data["base"]) > 0:
        _inheritance = " #of "
        _inheritance += data["base"][0]   # Nim does not support multiple inheritance

    _tmp = f'  {_name}* {{.{_include}importcpp: "{_name}"{_byref}.}} = object{_inheritance}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp    

def get_enum(data, include = None):
    _name = data["name"]
    
    _include = ""
    if include != None:
        _include = f'header: "{include}", '

    _type = get_nim_type(data["type"])
    _type = f"size:sizeof({_type})"

    #_items = [f'{i["name"]} = {i["value"]},\n{get_comment(i)}' for i in data["items"]]
    #_itemsComments = [get_comment(i)  for i in data[items]]
    #pprint(_items)
    _itemsTxt = ""
    _items = data["items"]
    n = len(_items)
    for i in range(len(_items)):
        _i = _items[i]
        _itemsTxt += f'    {_i["name"]} = {_i["value"]}'            
        if i<n-1:
            _itemsTxt += ","
        _itemsTxt += "\n"
        if _i["comment"] != None:
            _itemsTxt += get_comment(_i, n=6)

    #_items = ", ".join(_items)
    _tmp = f'  {_name}* {{.{_type},{_include}importcpp: "{_name}".}} = enum\n'
    if data["comment"] != None:
        _tmp += get_comment(data) + "\n"
    _tmp += _itemsTxt + "\n"
    return _tmp 

def get_const(data, include = None):
    _tmp = ""
    for i in data["items"]:
        _tmp += f'  {i["name"]}* = {i["value"]}\n'
        if i["comment"] != None:
            _tmp += get_comment(data) + "\n"
    return _tmp


def export_per_file(data, files = [], output= "occt", filter=None):
    #_fname = os.path.join(output,output) + ".nim"
    #_fp1 = open(_fname, "a+")

    _newfiles = []
    filtered_files = [i for i in files if i.startswith(filter)]
    for _file in filtered_files:
        _typedefs     = []
        _constructors = []
        _methods      = []
        _classes      = []
        _enums        = []
        _const        = []
        for item in data:
            if _file in item[0]:
                _tmpFile = _file.split(filter)[1]
                if item[1] == "constructor":
                    _constructors.append(get_constructor(item[2]))
                elif item[1] in ["method", "template"]:
                    _methods.append(get_method(item[2]))
                elif item[1] == "typedef":
                    _typedefs.append( get_typedef(item[2], _tmpFile))
                elif item[1] == "class":
                    _classes.append(get_class(item[2], _tmpFile))
                elif item[1] == "enum":
                    _enums.append(get_enum(item[2], _tmpFile))  
                elif item[1] == "const":
                    _const.append(get_const(item[2], _tmpFile))                                   
        _fname = ""
        _popfile = None
        if filter != None:
            _fname = _file.split(filter)[1]
            _popfile = _fname
        _fname = os.path.splitext(_fname)[0]
        _nimname = _fname + ".nim"
        _newfiles.append( _nimname)        
        _fname = os.path.join(output, _nimname)
        my_dict["const"] = my_dict["const"] + _const

        #if len(_typedefs) > 0 or len(_classes) > 0 or len(_enums) > 0:
        #    for _i in _enums:
        #        _fp1.write(_i)             
        #    for _i in _typedefs:
        #        _fp1.write(_i)
        #    for _i in _classes:
        #        _fp1.write(_i)                
        my_dict["enums"] = my_dict["enums"] + _enums
        my_dict["typedefs"] = my_dict["typedefs"] + _typedefs
        my_dict["class"] = my_dict["class"] + _classes

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

    #_fp1.close()

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


def get_params_from_node(mynode):
    _params = []
    for i in node.get_children():
        if i.kind == clang.cindex.CursorKind.PARM_DECL:
            _paramName = i.displayname

            _default = None
            # Getting default values in params
            for j in i.get_children():
                for k in j.get_children():                                  
                    if k.kind == clang.cindex.CursorKind.UNEXPOSED_EXPR:
                        for m in k.get_tokens():
                            _default = m.spelling
                    if k.kind == clang.cindex.CursorKind.INTEGER_LITERAL:
                        try:
                            _default = k.get_tokens().__next__().spelling 
                        except:
                            pass  
            _params.append((i.displayname, i.type.spelling, _default))                                                          
    return _params    


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
    _allfiles = glob.glob(_folder, recursive = True)
    _files = [f for f in _allfiles if os.path.isfile(f)]
    _dirs = [f for f in _allfiles if not os.path.isfile(f)]

    print("Root folder: ", _root)
    # Create folders if needed
    for i in _dirs:
        #os.path.join()
        _rel = os.path.relpath(i, _root)
        _folder = os.path.join(_dest,_rel)
        Path(_folder).mkdir(parents=True, exist_ok=True)
   
    #for root, dirs, files in os.walk(_folder): 
    _fname = os.path.join(_dest,_dest) + ".nim"
    _fp1 = open(_fname, "w")
    _fp1.write('{.passL: "-losg -losgSim -losgAnimation -losgTerrain -losgDB -losgText -losgFX -losgUI -losgGA -losgUtil -losgManipulator -losgViewer -losgParticle -losgVolume -losgPresentation -losgWidget -losgShadow", passC:"-I/usr/include/osg" .}\n\n')
    #_fp1.write("type\n")            
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
        tu = index.parse(include_file, args, None, opts)
   
        _all = []
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

                _params = get_params_from_node(node)
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
                _data["params"] = get_params_from_node(node) #_params
                _data["comment"] = node.brief_comment
                _all.append(( node.location.file.name, "method", _data ))

            # Classes
            if node.kind == clang.cindex.CursorKind.CLASS_DECL and node.is_definition():
                _data = { "name" : node.spelling,
                          "comment": node.brief_comment,
                          "base" : [] }

                for i in node.get_children():
                    if i.kind == clang.cindex.CursorKind.CXX_BASE_SPECIFIER:
                        _name = i.displayname
                        if "::" in _name:
                            _name = _name.split("::")[-1]
                        _data["base"].append( _name )
                        #if i.kind == clang.cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
                        #    print("access: ", i.spelling)
                    
                _all.append(( node.location.file.name, "class", _data ))

            # Types
            # Methods
            if node.kind == clang.cindex.CursorKind.TYPEDEF_DECL:
                _data = { "name" : node.displayname,
                          "underlying": node.underlying_typedef_type.spelling,
                          "is_function_proto": False}
                
                _data["params"] = get_params_from_node(node)
                _data["result"] = node.result_type.spelling

                _kind = node.underlying_typedef_type.kind
                if _kind == clang.cindex.TypeKind.POINTER:
                    _pointee = node.underlying_typedef_type.get_pointee()

                    if _pointee.kind == clang.cindex.TypeKind.FUNCTIONPROTO:
                        _result = _pointee.get_result().spelling
                        _data["result"] = _result
                        _data["is_function_proto"] = True

                _all.append(( node.location.file.name, "typedef", _data ))


            # CursorKind.CXX_METHOD CursorKind.FUNCTION_TEMPLATE CursorKind.OVERLOADED_DECL_REF
            if node.kind == clang.cindex.CursorKind.FUNCTION_TEMPLATE:
                _data = { "name" : node.spelling,
                          "comment": node.brief_comment }

                #_data = {"name" : _name}
                _data["result"] = node.result_type.spelling
                _data["class_name"] = node.semantic_parent.spelling
                _data["const_method"] = node.is_const_method()
                #_data["comment"] = node.brief_comment                                   
                _params = []
                _templParams = []
                for i in node.get_children():
                    #if _data["name"] == "addDrawable":
                    #    print(i.displayname)
                    if i.kind == clang.cindex.CursorKind.PARM_DECL:
                        _paramName = i.displayname
                        _params.append((i.displayname, i.type.spelling))
                    elif i.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
                        #if node.spelling == "replaceDrawable": 
                        _templParams.append(i.displayname)
                
                _data["params"] = _params
                _data["templParams"] = _templParams                


                # Parámetros
                _all.append(( node.location.file.name, "template", _data ))

            # ENUMS
            if node.kind == clang.cindex.CursorKind.ENUM_DECL:
                _data = { "name" : node.spelling,
                          "comment": node.brief_comment,
                          "type": node.enum_type.spelling }
                _items = []
                for i in node.get_children():
                    if i.kind == clang.cindex.CursorKind.ENUM_CONSTANT_DECL:
                        _items.append({"name":i.spelling,
                                       "comment": i.brief_comment,
                                       "value" : i.enum_value})

                _data["items"] = _items
                if _data["name"] != "":
                    _all.append(( node.location.file.name, "enum", _data ))
                else:
                    _all.append(( node.location.file.name, "const", _data ))

        # Only consider data associated to the file itself
        _all = [i for i in _all if i[0] == include_file]

        export_per_file( _all, files = [include_file], 
                         output=_dest,
                         filter=_root)

    _fp1 = open(_fname, "a+")

    if len(my_dict["const"]) > 0:
        _fp1.write("const\n")
        for txt in my_dict["const"]:
            _fp1.write(txt)
    _fp1.write("\n\n")

    if len(my_dict["type"]) > 0 or len(my_dict["enums"]) > 0 or \
       len(my_dict["typedefs"]) > 0 or len(my_dict["class"]) > 0 :   
        _fp1.write("type\n")
        for _i in my_dict["enums"]:
            _fp1.write(_i)             
        for _i in my_dict["typedefs"]:
            _fp1.write(_i)
        for _i in my_dict["class"]:
            _fp1.write(_i)  
        for k,v in my_dict.items():
            _fp1.write(f"  {v}\n\n")



    for _file in _files:
        _fname = _file.split(_root)[1]
        _fname = os.path.splitext(_fname)[0]
        _fp1.write(f'include "{_fname}.nim"\n')
    _fp1.close()            
