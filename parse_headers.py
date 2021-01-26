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

clang -Xclang -ast-dump -x c++ -I /usr/include/osg ./osg.hpp -fsyntax-only > osg.ast

https://github.com/StatisKit/AutoWIG/blob/master/src/py/autowig/libclang_parser.py
-----
TODO: 
Debe solventar los conflictos en el naming de los tipos presentes en osg_types. 
Por ejemplo, Type en StateAttribute y Type en Array

----
TODO: ¿por qué ByteArray (Type del fichero Array no va a osg_types)?

-----
TODO: operators
proc `[]=`[K, V](this: var StdMap[K, V]; key: K; val: V) {.
  importcpp: "#[#] = #", header: "<map>".}

-----
TODO: to check the Array file: python cpp2nim3.py "/usr/include/osg/Array" borrame

-----
TODO: si sale Clase & significa que hay que usar byref y en caso contrario: bycopy
-----
TODO: for some reason, the enum gets repited:
    tpInt64ArrayType = 37,
    tpLastArrayType = 37,

It needs to be replaced by something like:
   let tpLastArrayType:Type = tpInt64ArrayType

C++ allows using the same ID for different ID
-----
TODO: https://nim-lang.org/docs/tut2.html#object-oriented-programming-inheritance
Definición de tipos. Si usamos "object of <something>", en algún momento 
habrá que hacer un "object of RootObj". También hay que tener claro si usamos:
"ref object of RootObj"

----
TODO: /usr/include/osg/Referenced
proc constructdepends_on*[T, M](): depends_on {.constructor,importcpp: "depends_on<T, M>".}

----
TODO: probably, inlines, shouldn't be included. The same applies to private and protected!

-----
TODO: functions
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
#from yaml import load, dump
#from yaml import CLoader as Loader, CDumper as Dumper
#import networkx as nx

def print_line(node, field, spc, ident= 0):
    try:
        param = getattr(node, field)
        if callable(param):
            param = param()
        print(f"{spc}{field}: {param}")
        if isinstance( param, clang.cindex.Cursor):
            pp(_tmp, ident+ 4)
        elif isinstance(param, clang.cindex.Type):
            pptype(param, ident+4)

        elif hasattr(param,'__iter__'):#isinstance(param, collections.Iterable):
            pass
              
    except:
        print(f"{spc}{field}:  raises an exception!")    
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

def flatten(L):
    if len(L) == 1:
        if type(L[0]) == list:
            result = flatten(L[0])   
        else:
            result = L
    elif type(L[0]) == list:
        result = flatten(L[0]) + flatten(L[1:])   
    else:
        result = [L[0]] + flatten(L[1:])
    return result

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
        #_tmp = _tmp.capitalize()

        #my_dict["type"][_tmp] = "#" + f'{_tmp}* {{.importcpp: "{_a}", header: "<map>".}} [K] = object'
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
    if txt[0] == "_":
        txt = "prefix" + txt[1:]
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
        else:
            _params += f'a{n:02d}: '
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

def get_template_parameters(methodname):  # ÑAPA
    if '<' in methodname and '>' == methodname[-1]:
        _a, _b = methodname.split('<')
        _b = _b[:-1]
        return (_a, f"[{_b}]")
    else:
        return(methodname, '')

def get_constructor(data):
    _params = export_params(data["params"])   
    _tmp = ""
    if _params != "":
        _tmp = "(@)"

    # Templates
    methodname, templateparams = get_template_parameters(data["name"])
    _tmp = f'proc construct{methodname}*{templateparams}({_params}): {data["class_name"]} {{.constructor,importcpp: "{data["fully_qualified"]}{_tmp}".}}\n'
    _tmp += get_comment(data)  + "\n"
    return _tmp    

def get_method(data):
    # Parameters
    _params = export_params(data["params"])
    if _params != "":
        _params = ", " + _params

    # - Bear in mind the 'in-place' case
    _classname = data["class_name"]
    if not data["const_method"]:
        _classname = f"var {_classname}"

    _params = f'this: {_classname}{_params}'

    # Returned type
    _return = ""
    if data["result"] not in ["void", "void *"]:
        _result = data["result"].strip()
        if _result.startswith("const "):
            _result = _result[6:]
        if _result[-1] == "&":
            _result = _result[:-1].strip()
        _result = get_nim_type( _result )
        _return = f': {_result}'

    # Method name (lowercase the irst letter)
    _methodName = data["name"]
    _methodName = _methodName[0].lower() + _methodName[1:]
    _importName = data["name"]
    #_importName = data["fully_qualified"]    

    # Operator case
    _isOperator = False
    if _importName.startswith("`") and _importName.endswith("`"):
        _importName = _importName[1:-1]
        _importName = f"# {_importName} #"
        _isOperator = True
    
    # Templates
    _templParams = ""
    if "templParams" in data:
        if len(data["templParams"]) > 0:
            _templParams = "[" + ";".join( data["templParams"] ) + "]"
    _methodName = clean(_methodName)
    if _isOperator and _methodName in ["`=`"]:
        _tmp = f'proc {_methodName}*{_templParams}({_params})  {{.importcpp: "{_importName}".}}\n'
    elif _isOperator and _methodName in ["`[]`"]:
        _importName = "#[#]"
        _tmp = f'proc {_methodName}*{_templParams}({_params})  {{.importcpp: "{_importName}".}}\n'  
    else:
        _tmp = f'proc {_methodName}*{_templParams}({_params}){_return}  {{.importcpp: "{_importName}".}}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp

def get_typedef(name, data, include = None):   # TODO: añadir opción si no está referenciado, comentar
    #_type = ""
    #if "underlying_deps" in data:
    #    print(data["underlying"])
    #else:
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
        _name = clean(name)
        _name = _name[0].upper() + _name[1:]
        
        return f'  {_name}* {{.{_include}importcpp: "{data["fully_qualified"]}".}} = {_tmp}\n'
    else:
        _name = clean(name)  
        _name = _name[0].upper() + _name[1:]              
        return f'  {_name}* {{.{_include}importcpp: "{data["fully_qualified"]}".}} = {_type}\n'
    #_data[_file]["typedefs"].append((i["name"], _type))

def get_class(name, data, include = None, byref = True):
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

    _nameClean = clean(name)
    _name = data["fully_qualified"]
    _template = ""
    if len(data["template_params"]) > 0:
        _tmpList = []
        for i in data["template_params"]:
            if type(i) == tuple:
                _tmp = i[0] + ":" + get_nim_type(i[1])
                _tmpList.append(_tmp)
            else:
                _tmpList.append(i)
        _template = f'[{"; ".join(_tmpList)}]'

        #_template = f'[{", ".join(data["template_params"])}] '
    _tmp = f'  {_nameClean}*{_template} {{.{_include}importcpp: "{_name}"{_byref}.}} = object{_inheritance}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp    

def get_struct(name, data, include = None):
    _include = ""
    if include != None:
        _include = f'header: "{include}", '
    _byref = ", byref" 

    _nameClean = clean(name)
    _name = data["fully_qualified"]
    _template = ""
    """
    if len(data["template_params"]) > 0:
        _tmpList = []
        for i in data["template_params"]:
            if type(i) == tuple:
                _tmp = i[0] + ":" + get_nim_type(i[1])
                _tmpList.append(_tmp)
            else:
                _tmpList.append(i)
        _template = f'[{"; ".join(_tmpList)}]'

        #_template = f'[{", ".join(data["template_params"])}] '
    """
    #_tmp = f'  {_nameClean}*{_template} {{.{_include}importcpp: "{_name}"{_byref}.}} = object{_inheritance}\n'
    _tmp = f'  {_nameClean}* {{.{_include}importcpp: "{_name}".}} = object\n'
    _tmp += get_comment(data) + "\n"
    return _tmp

def get_enum(name, data, include = None):
    #pprint(data)
    _name = name.split("::")[-1]
    _prefix = "" #remove_vowels( _name )

    _include = ""
    if include != None:
        _include = f'header: "{include}", '

    _type = get_nim_type(data["type"])
    _type = f"size:sizeof({_type})"

    _itemsTxt = ""
    _items = data["items"]
    #pprint(_items)
    n = len(_items)
    for i in range(len(_items)):
        _i = _items[i]
        #print(_i)
        _itemsTxt += f'    {_prefix}{_i["name"]} = {_i["value"]}'            
        if i<n-1:
            _itemsTxt += ","
        _itemsTxt += "\n"
        if _i["comment"] != None:
            _itemsTxt += get_comment(_i, n=6)

    #_items = ", ".join(_items)

    _tmp = f'  {_name}* {{.{_type},{_include}importcpp: "{name}", pure.}} = enum\n'
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
    for i in mynode.get_children():
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

def fully_qualified(c):
    if c is None:
        return ''
    elif c.kind == clang.cindex.CursorKind.TRANSLATION_UNIT:
        return ''
    else:
        res = fully_qualified(c.semantic_parent)
        if res != '':
            return res + '::' + c.spelling
    return c.spelling

NORMAL_TYPES = ["void", "long", "unsigned long", "int", "size_t", "long long", "long double", 
                "float", "double", "char", "signed char", "unsigned char", "unsigned short", 
                "unsigned int", "unsigned long long", "char*", "bool" ]

def cleanit(tmp):
    if tmp.startswith("const "):
        tmp = tmp[6:]
    if tmp[-1] in ["&", "*"]:
        tmp = tmp[:-2]    
    return tmp

def get_nodes(node,depth=0):
    """Traverse the AST tree
    """
    yield (depth, node)
    for child in node.get_children():
        yield from get_nodes(child, depth = depth+1)

def get_template_dependencies(tmp):
    result = []
    _tmp = cleanit(tmp)
    if _tmp[-1] == ">" and "<" in _tmp: # In case is based on a template
        _tmp = [i.split('>') for i in _tmp.split('<')]
        _tmp = flatten(_tmp)
        _tmp = [i.split(',') for i in _tmp]
        _tmp = flatten(_tmp)
        _tmp = [i.strip() for i in _tmp if i.strip() != '']
        _tmp = [cleanit(i) for i in _tmp if not i.isdigit()]
        return _tmp
            
    return [_tmp]


def parse_include_file(filename, dependsOn, provides):
    """This will parse a include file and return the data
    """
    #_data = {"filename" : filename, "imports" : [] }
    _data = []

    _index = clang.cindex.Index.create()
    _args = ['-x', 'c++',  f"-I{_folder}"] 
    #opts = TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES # a bitwise or of TranslationUnit.PARSE_XXX flags.
    _opts = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD | \
            clang.cindex.TranslationUnit.PARSE_INCOMPLETE | \
            clang.cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
    _tu = _index.parse(filename, _args, None, _opts)

    _consts, _enums, _repeated = _parse_enums(filename, _tu)  # (list, dict, dict)
    for i in _consts:
        _data.append( (filename, "const", i))
        #pprint(i)
    for key,value in _enums.items():
        _data.append( (filename, "enum", key, value))
    for key,value in _repeated.items():
        _data.append( (filename, "repeated", key, value))

    _typedefs     = _parse_typedef(filename, _tu) # dict
    for key,value in _typedefs.items():
        _data.append( (filename, "typedef", key, value))    
    _classes      = _parse_class(filename, _tu)    # 
    for key,value in _classes.items():
        _data.append( (filename, "class", key, value))
    _structs      = _parse_struct(filename, _tu)
    for key,value in _structs.items():
        _data.append( (filename, "struct", key, value))    
    _constructors = _parse_constructors(filename, _tu)
    for i in _constructors:
        #pprint(i)
        _data.append( (filename, "constructor", i["fully_qualified"], i))       
    _methods      = _parse_methods(filename, _tu)
    for i in _methods:
        _data.append( (filename, "method", i["fully_qualified"], i)) 


    _dependsOn = _find_depends_on( filename, _data )
    #_data.append( (filename, "dependsOn", _dependsOn)) 

    _provides  = _find_provided( filename, _data, _dependsOn )
    #_data.append( (filename, "provides", _provides))     
 
    _missing   = _missing_dependencies( filename, _data, _dependsOn, _provides )
    #_data.append( (filename, "missing", _missing))  
    #for key,value in _missing.items():
    #    _data.append( (filename, "missing", key, value))      
    return _data, _dependsOn, _provides, _missing


def _parse_enums(filename, _tu):
    """This function aims to extract all the anonymous enums"""
    _consts = []
    _repeated = {}
    _enums = {}
    for depth,node in get_nodes( _tu.cursor, depth=0 ):
        _tmp = {}
        _isConst = False
        if node.kind == clang.cindex.CursorKind.ENUM_DECL and \
           node.location.file.name == filename:
            _typeName = fully_qualified(node.referenced)
            if node.spelling == "":
                _isConst = True
            else:
                _isConst = False
            _tmp = {"comment": node.brief_comment,
                    "type": node.enum_type.spelling,
                    "items" : []}
            for _depth, n in get_nodes(node, depth):
                if n.kind == clang.cindex.CursorKind.ENUM_CONSTANT_DECL:                        
                    _tmp["items"].append( { "name"   : n.spelling,
                                            "comment": n.brief_comment,
                                            "value"  : n.enum_value} )

            if _isConst:
                #_tmp.pop("name")
                _consts.append(_tmp) # Just in case there are several const definitions
            else:
                # Sort list
                _values = [i["value"] for i in _tmp["items"]]
                _values = list(set(_values))
                _values.sort()
                _names = [i["name"] for i in _tmp["items"]]                    
                _new = []
                for i in _values:
                    for item in _tmp["items"]:
                        if item["value"] == i:
                            _new.append( item )
                            _names.remove(item["name"])
                            break
                for _name in _names:
                    for item in _tmp["items"]:
                        if item["name"] == _name:
                            _repeated[_name] = item
                _tmp["items"] = _new
                _enums.update({_typeName : _tmp})
    return _consts, _enums, _repeated

def _parse_typedef(filename, _tu):
    _typedefs = {}
    for depth,node in get_nodes( _tu.cursor, depth=0 ):
        if node.kind in [clang.cindex.CursorKind.TYPEDEF_DECL] and \
            node.location.file.name == filename:  
            _name = node.displayname
            _tmp = { 
                        "underlying": node.underlying_typedef_type.spelling,
                        "is_function_proto": False,
                        "fully_qualified": fully_qualified(node.referenced),
                        "result": node.result_type.spelling              
                    }


            # Underlying dependencies
            _tmp["underlying_deps"] = get_template_dependencies(_tmp["underlying"])


            # The typedef might be for a function
            _tmp["params"] = get_params_from_node(node)
            
            _kind = node.underlying_typedef_type.kind
            if _kind == clang.cindex.TypeKind.POINTER:
                _pointee = node.underlying_typedef_type.get_pointee()

                if _pointee.kind == clang.cindex.TypeKind.FUNCTIONPROTO:
                    _result = _pointee.get_result().spelling
                    _tmp["result"] = _result
                    _tmp["is_function_proto"] = True                
            _typedefs.update({_name : _tmp})
    return _typedefs

def _parse_class(filename, _tu):
    """Parse classes (not forward declarations)"""
    _classes = {}
    for depth,node in get_nodes( _tu.cursor, depth=0 ):
        if node.kind in [clang.cindex.CursorKind.CLASS_DECL, clang.cindex.CursorKind.CLASS_TEMPLATE] and \
            node.is_definition() and node.location.file.name == filename:             
            _tmp = { "name" : node.spelling,
                        "comment": node.brief_comment,
                        "base" : [],
                        "fully_qualified": fully_qualified(node.referenced),
                        "template_params" : []
                    }                    
            #access_specifier: AccessSpecifier.PUBLIC
            #availability: AvailabilityKind.AVAILABLE
            for _, n in get_nodes( node, depth=depth ):
                if n.kind == clang.cindex.CursorKind.CXX_BASE_SPECIFIER:
                    _tmp["base"].append(n.displayname)

            # Get template parameters
            if node.kind == clang.cindex.CursorKind.CLASS_TEMPLATE:
                #print(depth)         
                for _depth, n in get_nodes(node, depth):
                    #print(_depth, n.spelling, n.kind)
                    if n.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
                        _flag = False
                        _tmp["template_params"].append(n.spelling)
                    elif n.kind == clang.cindex.CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
                        _templateParam = (n.spelling,n.type.spelling)
                        _flag = False
                        _tmp["template_params"].append(_templateParam)                            
                    elif n.kind in [clang.cindex.CursorKind.CLASS_TEMPLATE, clang.cindex.CursorKind.TYPE_REF]:
                        pass 
                    else:
                        break

            _name = _tmp["name"]
            _tmp.pop("name")
            _classes[_name] = _tmp          
    return _classes

def _parse_struct(filename, _tu):
    _structs = {}
    for depth,node in get_nodes( _tu.cursor, depth=0 ):
        if node.kind == clang.cindex.CursorKind.STRUCT_DECL and \
           node.location.file.name == filename:
            _tmp = { "name" : node.spelling,
                        "comment": node.brief_comment,
                        "base" : [],
                        "fully_qualified": fully_qualified(node.referenced),
                        "template_params" : []
                    }
            _structs.update( {node.spelling : _tmp} )              
    return _structs

def _parse_constructors(filename, _tu):
    _constructors = []
    for depth,node in get_nodes( _tu.cursor, depth=0 ):
        if node.kind in [clang.cindex.CursorKind.CONSTRUCTOR] and \
            node.location.file.name == filename:   
            _tmp = { "name" : node.spelling,
                "class_name": node.semantic_parent.spelling,
                "comment": node.brief_comment,
                "fully_qualified": fully_qualified(node.referenced) }
            _tmp["params"] = get_params_from_node(node)
            _constructors.append(_tmp)
    return _constructors

def _parse_methods(filename, _tu):
    """Parse methods and operators"""
    _methods = []
    for depth,node in get_nodes( _tu.cursor, depth=0 ):
        if node.kind in [clang.cindex.CursorKind.CXX_METHOD] and \
            node.location.file.name == filename:    
            _name = node.spelling
            if _name.startswith("operator"):
                _tmp = _name[8:]
                if re.match("[+-=*\^/]+", "+-+=*^"):
                    _name = f'`{_tmp}`'

            _tmp = {"name" : _name,
                    "fully_qualified" : fully_qualified(node.referenced),
                    "result" : node.result_type.spelling,
                    "class_name": node.semantic_parent.spelling,
                    "const_method": node.is_const_method(),
                    "comment" : node.brief_comment,
                    "file_origin" : node.location.file.name }
                
            #print(_tmp["result"])                    
            #pprint(_tmp["result_deps"])
            #if "<" in _tmp["result"]:
            _tmp["result_deps"] = get_template_dependencies(_tmp["result"])
            #    pprint(_tmp)
            # Methods dependencies for results

            _tmp["params"] = get_params_from_node(node)
            _methods.append(_tmp)
    return _methods

def _find_depends_on(filename, _data):
    """Find all dependences in the file"""
    _dependsOn = []
    for _tmp in _data:
        if len(_tmp) == 4:
            _filename, _type, _name, _values = _tmp
            if _filename == filename:
                if _type in ["method", "constructor"]:                     
                    for param in _values["params"]:
                        _tmp1 = get_template_dependencies(param[1])
                        if _tmp1 != []:
                            for j in _tmp1:
                                _dependsOn.append(j)
                        else:
                            _dependsOn.append(cleanit(param[1]))

                        if param[2] != None:
                            _dependsOn.append(param[2])

                    if "result" in _values:
                        if _values["result"] != None:
                            if _values["result_deps"] != []:
                                for j in _values["result_deps"]:
                                    _dependsOn.append( j )
                            else:
                                _dependsOn.append(cleanit(_values["result"]))
                elif _type in ["typedefs"]:      
                    if _values["underlying_deps"] != []:
                        for _i in _values["underlying_deps"]:
                            _dependsOn.append( _values )
                    else:            
                        _tmp = cleanit(_values["underlying"])
                        _dependsOn.append( _tmp )
                
                # Some classes are templates; and those params might depend on other types
                elif _type in ["class"]:
                    if "template_params" in _values:
                        for i in _values["template_params"]:
                            if type(i) == tuple:
                                _dependsOn.append( i[1] )
                                
    return set(_dependsOn)


def _find_provided(filename, _data, _dependsOn):
    """Find all types that the file might provide to others"""
    # Dependencies
    _provides = []
    for _tmp in _data:  #_name, _values
        if len(_tmp) == 4:
            _filename, _type, _name, _values = _tmp
            if _filename == filename:
                if _type == "const":    
                    for item in _values["items"]:
                        #_dependsOn = dependsOn[_filename]
                        if item["name"] in _dependsOn:
                            _provides.append(item["name"])
                elif _type == "enum":
                    for i in _values["items"]:
                        _provides.append((i["name"],_name))
                    _provides.append(_name)
                elif _type == "class":
                    _provides.append(_values["fully_qualified"])
                elif _type == "struct":
                    _provides.append(_values["fully_qualified"])            
                elif _type == "typedef":
                    _provides.append(_values["fully_qualified"])

    return set(_provides)

def _missing_dependencies(filename, _data, _dependsOn, _provides):
    _missing = set([])
    #_dependsOn = dependsOn.get(filename,[])
    #_provides = provides.get(filename, [])
            
    for i in _dependsOn:
        if i not in NORMAL_TYPES:
            if i not in _provides:
                _tmp = [k[0] for k in _provides if type(k) is tuple]
                if i not in _tmp:
                    _missing.add( i )
    return _missing


def export_txt(_data, filter = {}, dependencies = {}, root= "/", shared = None ):
    # Filtering consts, enums, typedefs and type
    _filter = { "const"   : [],
                "enum"    : [], 
                "typedef" : [],
                "class"   : [],
                "struct"  : []}

    if _data["filename"] in filter:
        _set = filter[ _data["filename"] ]
        
        for i in _data["consts"]:
            for item in i["items"]:
                if item["name"] in _set:
                    _filter["const"].append(item["name"])                  
        for i,_ in _data["enums"].items():
            if i in _set:
                _filter["enum"].append(i)

        for k,v in _data["typedefs"].items():
            if v["fully_qualified"] in _set:
                _filter["typedef"].append(v["fully_qualified"])
                # We also consider their dependencies (they will be handled in the root file)
                if "underlying_deps" in v:
                    for _i in v["underlying_deps"]:
                        if _i in _data["classes"]:
                            _v = _data["classes"][_i]
                            _filter["class"].append( _v["fully_qualified"] )
        for k,v in _data["classes"].items():
            if v["fully_qualified"] in _set:
                _filter["class"].append(v["fully_qualified"])

        for k,v in self.structs.items():
            if v["fully_qualified"] in _set:
                _filter["struct"].append(v["fully_qualified"])
        
    _filename = _data["filename"].split(root)[-1]
    _txt = ""

    if len(dependencies.keys()) > 0:
        _txt += f'import {shared}\n'            
        for i in dependencies.keys():
            _tmp = i.split(root)[-1]
            _tmp = _tmp.split('.')[0]
            _types = ', '.join(dependencies[i])
            #_txt += f'import {_tmp}  # provides: {_types}\n'
            _txt += f'  # File: {_tmp}  was providing: {_types}\n'

    _consts = _data["consts"]
    # Remove shared consts
    if (len(_data["consts"]) - len(_filter["const"]) )> 0:
        _txt += "const\n"
        for i in _data["consts"]:
            if i not in _filter["const"]:
                _txt += get_const(i)
        _txt += "\n\n"
    _n = len(_filter["enum"]) + len(_filter["typedef"]) + len(_filter["class"]) + len(_filter["struct"])

    if (len(_data["typedefs"]) + len(_data["classes"]) + len(_data["enums"]) + len(_data["structs"]) - _n) > 0:
        _txt += "type\n"
        if len(_data["enums"]) > 0:
            for name,data in _data["enums"].items():
                if name not in _filter["enum"]:
                    _txt += get_enum(name,data, _filename)

        # Classes go before typedefs (typedefs might depend on them)
        if len(_data["classes"]) > 0:
            for name, data in _data["classes"].items():
                if data["fully_qualified"]  not in _filter["class"]:                    
                    _txt += get_class(name,data, _filename)

        if len(_data["structs"]) > 0:
            for name, data in _data["structs"].items():
                if data["fully_qualified"]  not in _filter["struct"]:                    
                    _txt += get_struct(name,data, _filename)

        if len(_data["typedefs"]) > 0:
            for name, data in _data["typedefs"].items():
                if data["fully_qualified"] not in _filter["typedef"]:                    
                    _txt += get_typedef(name,data, _filename)

        _txt += "\n\n"

    _flag = (len(_data["constructors"]) + len(_data["methods"])) >0
    if _flag:
        _txt += f'{{.push header: "{_filename}".}}\n\n'
    for i in _data["constructors"]:
        _txt += get_constructor(i)

    for i in _data["methods"]:
        _txt += get_method(i)

    if _flag:
        _txt += f'{{.pop.}}  # header: "{_filename}"\n'
    
    return _txt

#==============================================================
if __name__ == '__main__':
    # Read the command line: it takes a glob and a destination
    _folder = sys.argv[1]
    _dest = sys.argv[2]
    _path = os.getcwd()
    _destination_folder = os.path.join(_path, _dest)
    _delete_folder = os.path.join(_dest, "deleteme")    
    if not os.path.isdir(_destination_folder):
        os.mkdir(_destination_folder)       
    if not os.path.isdir(_delete_folder):    
        os.mkdir(_delete_folder) 

    # Get the files list
    _root = get_root(_folder)    
    _allfiles = glob.glob(_folder, recursive = True)
    _files = [f for f in _allfiles if os.path.isfile(f)]
    _dirs  = [f for f in _allfiles if not os.path.isfile(f)]

    print("Root folder: ", _root)
    # Create folders if needed
    for i in _dirs:
        _rel = os.path.relpath(i, _root)
        _folder = os.path.join(_dest,_rel)
        Path(_folder).mkdir(parents=True, exist_ok=True)
   
    # Start parsing all the include files
    files = []
    _dependsOn = {}
    _provides = {}
    _missing = {}
    _nTotal = len(_files)
    _n = 1
    for include_file in _files:
        print(f"Parsing ({_n}/{_nTotal}): {include_file}")
        _n += 1
        _data, _deps, _prov, _miss = parse_include_file(include_file, _dependsOn, _provides)
        #pprint(pf)
        #files[include_file] = pf
        files = files + _data
        _dependsOn[include_file] = _deps
        _provides[include_file]  = _prov
        _missing[include_file]   = _miss

    _dict = { "includes": files,
              "dependsOn" : _dependsOn,
              "provides" : _provides,
              "missing"  : _missing
            }

    import pickle
    _files_name = os.path.join(_delete_folder, 'files.pickle')
    fp = open(_files_name, 'wb')
    pickle.dump(_dict, fp)
    fp.close()
