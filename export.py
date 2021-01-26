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
import string
import os
import glob
import textwrap
import re
from pprint import pprint

def get_nim_type( c_type, rename = {} ):   
    c_type = c_type.strip()

    isVar = True
    if c_type.startswith("const"):
        c_type = c_type[5:].strip()
        isVar = False

    if not c_type.endswith("&"):
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
        #for _repeatedTypes, _list in repeated.items():
        #    if _tmp == _repeatedTypes:
        #        _tmp = ".".join( _a.split("::")[-2:] )
        #if c_type == "Array::Type":
        #    print(_a)
        for somename in rename.keys():
            #print(somename)
            if somename.endswith( _a ):
                _tmp = rename[somename]
        #if _a in rename:
        #    _tmp = rename[_a]


        #my_dict["type"][_tmp] = "#" + f'{_tmp}* {{.importcpp: "{_a}", header: "<map>".}} [K] = object'
        if _tmp[-1] == "*":
            _tmp = f"ptr {_tmp[:-1]}"
        
        if _b != "":
            # There may be several types
            _b = _b.split(", ")
            _b = [get_nim_type(_i, rename) for _i in _b]
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

def export_params(params, rename = {}):
    _params = ""
    n = 0
    for p in  params:
        if n > 0:
            _params += ", "
        if p[0]:
            _params += clean(p[0]) + ": "
        else:
            _params += f'a{n:02d}: '
        _type = get_nim_type(p[1], rename)
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

def get_constructor(data,rename = {}):
    _params = export_params(data["params"], rename)   
    _tmp = ""
    if _params != "":
        _tmp = "(@)"

    # Templates
    methodname, templateparams = get_template_parameters(data["name"])
    _tmp = f'proc construct{methodname}*{templateparams}({_params}): {data["class_name"]} {{.constructor,importcpp: "{data["fully_qualified"]}{_tmp}".}}\n'
    _tmp += get_comment(data)  + "\n"
    return _tmp    

def get_method(data,rename = {}):
    # Parameters
    _params = export_params(data["params"], rename)
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
        _result = get_nim_type( _result, rename )
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

def get_typedef(name, data, include = None, rename={}):   # TODO: añadir opción si no está referenciado, comentar
    #_type = ""
    #if "underlying_deps" in data:
    #    print(data["underlying"])
    #else:
    _type = get_nim_type( data["underlying"], rename )
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
            _result = get_nim_type( _result, rename )
            _return = f': {_result}'        
        _params = export_params(data["params"], rename)
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

def get_class(name, data, include = None, byref = True, rename = {}):
    #)
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
            #if name == "TemplateArray":
            #    print(i)
            #    pprint(rename)
            if type(i) == tuple:
                _tmp = i[0] + ":" + get_nim_type(i[1], rename )
                _tmpList.append(_tmp)
            else:
                _tmpList.append(i)
        _template = f'[{"; ".join(_tmpList)}]'

        #_template = f'[{", ".join(data["template_params"])}] '
    _tmp = f'  {_nameClean}*{_template} {{.{_include}importcpp: "{_name}"{_byref}.}} = object{_inheritance}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp    

def get_struct(name, data, include = None, rename={}):
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
                _tmp = i[0] + ":" + get_nim_type(i[1], rename)
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

def get_enum(name, data, include = None, rename = {}):
    #pprint(data)
    _name = name.split("::")[-1]    
    if name in rename:
        _name = rename[name]


    _prefix = "" #remove_vowels( _name )

    _include = ""
    if include != None:
        _include = f'header: "{include}", '

    _type = get_nim_type(data["type"], rename)
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
        result = _tmp           
    return result

def export_txt(filename, data,  root= "/", rename = {}):
    _txt = ""
    #if "AlphaFunc" in filename:
    #    _t = [i for i in data if "AlphaFunc" in i[0]]
    #    _t = [i for i in data if filename == i[0]]        
    #    pprint(_t)    
    #    print(filename)
    # Pragma
    _pragma = [i for i in data if i[0] == filename and i[2] == "pragma"]    
    for i in _pragma:
        _txt += i[4] + "\n\n"

    # Imports
    _imports = [i[3] for i in data if i[0] == filename and i[2] == "import"]
    #if len(_imports) > 0:
    for items in _imports:
        _items = [os.path.splitext( i )[0] for i in items]
        _tmp = ", ".join(_items)
        _txt += f"import {_tmp}\n"
    if len( _imports ) > 0:
        _txt += "\n\n"
     

    #_consts = []
    #if "consts" in _data:
    #    _consts = _data["const"]
    #_filters = []
    #if "const" in _filter:
    #    _filters = _filter["const"]
    # Consts
    _consts = [i[3] for i in data if i[0] == filename and i[2] == "const"]    
    if len(_consts) > 0:
        _txt += "const\n"
    for i in _consts:
        _txt += get_const(i)
    if len(_consts) > 0:            
        _txt += "\n\n"


    #_n = len(_filter["enum"]) + len(_filter["typedef"]) + \
    #     len(_filter["class"]) + len(_filter["struct"])
    _n = [i for i in data if i[0] == filename and i[2] in ["enum", "class", "struct", "typedef"]] 
    #if (len(_data.get("typedefs",[])) + len(_data.get("classes", [])) + \
    #    len(_data.get("enums",[])) + len(_data.get("structs",[])) - _n) > 0:
    if len(_n) > 0:
        _txt += "type\n"

    # Enums
    _enums = [i for i in data if i[0] == filename and i[2] == "enum"] 
    for _, _filename, _, name, values in _enums:
        _fname = os.path.relpath( _filename, root )
        _txt += get_enum( name, values, _fname, rename = rename)

    # Classes
    _classes = [(i[1], i[3],i[4]) for i in data if i[0] == filename and i[2] == "class"]     
    for _filename, name, values in _classes:
        _fname = os.path.relpath( _filename, root )
        _txt += get_class( name, values, _fname, rename = rename)   

    # Structs
    _structs = [(i[1], i[3], i[4]) for i in data if i[0] == filename and i[2] == "struct"] 
    for _filename, name, values in _structs:
        _fname = os.path.relpath( _filename, root )
        _txt += get_struct( name, values, _fname, rename = rename) 

    # Typedefs
    _typedefs = [(i[1], i[3],i[4]) for i in data if i[0] == filename and i[2] == "typedef"] 
    for _filename, name, values in _typedefs:
        _fname = os.path.relpath( _filename, root )
        _txt += get_typedef(name, values, _fname, rename = rename)
    
    if len(_n) > 0:
        _txt += "\n\n"

    _n = [i for i in data if i[0] == filename and i[2] in ["constructor", "method"]]

    if len(_n) > 0:
        _fname = os.path.relpath( _n[0][1], root )        
        _txt += f'{{.push header: "{_fname}".}}\n\n'

    _constructors = [i for i in data if i[0] == filename and i[2] == "constructor"]
    for i in _constructors:
        _txt += get_constructor(i[4], rename)        

    _methods = [i for i in data if i[0] == filename and i[2] == "method"]
    #if "AlphaFunc" in filename:
    #    print("dntro")
    #    pprint(_methods)
    #    pprint( [i for i in data if i[0] == filename ]  )
    for i in _methods:
        _txt += get_method(i[4], rename)

    if len(_n) > 0:
        _fname = os.path.relpath( _n[0][1], root )        
        _txt += f'{{.pop.}}  # header: "{_fname}"\n'
    
    return _txt
