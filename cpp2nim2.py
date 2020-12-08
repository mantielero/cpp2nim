#!/usr/bin/env python
""" Usage: call with <filename> <typename>
python cpp2nim.py "/usr/include/opencascade/gp_*.hxx" occt

>>> import clang.cindex
>>> index = clang.cindex.Index.create()
>>> tu = index.parse("/usr/include/opencascade/gp_Pnt.hxx", ['-x', 'c++',  "-I/usr/include/opencascade"], None, clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)

clang -Xclang -ast-dump -fno-diagnostics-color miniz.c

TODO: si sale Clase & significa que hay que usar byref y en caso contrario: bycopy
"""

import sys
import clang.cindex
import string
import os
import glob
import textwrap
import re
from pprint import pprint
import oyaml as yaml
#import networkx as nx


#function_calls = []             # List of AST node objects that are function calls
function_declarations = []      # List of AST node objects that are fucntion declarations


def display(node, depth=0 ):
    global CURRENT_FILE
    fname = str(node.location.file).strip()
    if  fname != CURRENT_FILE:
        print("\n\n",fname)
    CURRENT_FILE = fname
    tmp = os.path.split(str(fname))[1]
    ident = ">" * (depth)
    if tmp == 'miniz.h':
       #if node.kind == clang.cindex.CursorKind.TYPEDEF_DECL:
        print("{:<10} [{:6}/{:3}] {}{:<15}: name={}".format(tmp, node.location.line, node.location.column, ident, node.kind.name, node.displayname or node.spelling) )

           #print("   KIND:    ", node.kind)
           #print("   SPELLING: ", node.spelling)
           #print("      kind: ", node.type.element_type)
           #print(dir(node))
           #print("   X:", node.underlying_typedef_type.spelling)
           #print("   COMMENT: ", node.raw_comment)




           #print("   ", node)
# 'access_specifier', 'availability', 'brief_comment', 'canonical', 'data', 'displayname', 'enum_type', 'enum_value', 'exception_specification_kind', 'extent', 'from_cursor_result', 'from_location', 'from_result', 'get_arguments', 'get_bitfield_width', 'get_children', 'get_definition', 'get_field_offsetof', 'get_included_file', 'get_num_template_arguments', 'get_template_argument_kind', 'get_template_argument_type', 'get_template_argument_unsigned_value', 'get_template_argument_value', 'get_tokens', 'get_usr', 'hash', 'is_abstract_record', 'is_anonymous', 'is_bitfield', 'is_const_method', 'is_converting_constructor', 'is_copy_constructor', 'is_default_constructor', 'is_default_method', 'is_definition', 'is_move_constructor', 'is_mutable_field', 'is_pure_virtual_method', 'is_scoped_enum', 'is_static_method', 'is_virtual_method', 'kind', 'lexical_parent', 'linkage', 'location', 'mangled_name', 'objc_type_encoding', 'raw_comment', 'referenced', 'result_type', 'semantic_parent', 'spelling', 'storage_class', 'tls_kind', 'translation_unit', 'type', 'underlying_typedef_type', 'walk_preorder', 'xdata'

# Traverse the AST tree
def get_nodes(node,depth=0):
    yield (depth, node)
    for child in node.get_children():
        yield from get_nodes(child, depth = depth+1)



def emit_nim_TYPEDEF_DECL(node):
    """
    TODO:
      {.impminiz.}
      {.cdecl.}

    typedef unsigned long mz_ulong;
    mz_ulong* {.impminiz.} = culong

    """
    #print("# TODO: missing {.impminiz.} and {.cdecl.}")
    name = node.displayname+"*"
    #print(name)
    tipo = node.underlying_typedef_type.spelling
    if "(" in tipo:
        col = node.location.column

        inputs = []
        output = []
        for i in node.get_children():
            if i.location.column < col:
                if node.kind.PARM_DECL:
                    output = i.spelling
            else:
                inputs.append( (i.spelling, get_nim_type(i.type.spelling)) )
        #if output == []:

        #print(inputs)
        inputs = [" {}: {}".format(input[0],input[1]) for input in inputs]
        inputs = ", ".join( inputs )
        nimcode = "{} = proc( {} ):output".format(name,inputs, output)
        #print( nimcode )
        return nimcode
    # ENUM
    elif tipo[0:4] == "enum":
        nimcode = "  {} = enum\n".format(name)
        for i in node.get_children():
            if i.kind == clang.cindex.CursorKind.ENUM_DECL:
               for j in i.get_children():
                  if j.kind == clang.cindex.CursorKind.ENUM_CONSTANT_DECL:
                      _name = j.displayname
                      _value = None

                      for k in j.get_children():
                          if k.kind == clang.cindex.CursorKind.INTEGER_LITERAL:
                              _value = [m.spelling for m in k.get_tokens()][0]
                      if _value != None:
                          _line = "    {} = {},\n".format(_name,_value)
                      else:
                          _line = "    {},\n".format(_name)
                      nimcode += _line
        if nimcode[-2:] == ',\n':
           nimcode = nimcode[0:-2]+"\n"
        return nimcode

    # NORMAL
    else:
        tipomod = get_nim_type(tipo)
        if tipomod == None:
            print("TODO : ", tipo)
        return "{} = {}".format(name, tipomod )

def get_nim_type( c_type ):
    c_type = c_type.strip()
    #print(c_type)
    
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
    if c_type in ["short", "int", "long", "signed", "unsigned", "size_t"]:
        return "cint"
    if c_type in ["unsigned long"]:
        return "culong"
    if c_type in ["float"]:
        return "cfloat"        
    if c_type in ["double"]:
        return "cdouble"

    if isVar:
        c_type = f"var {c_type}"
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
    #print("-----------")
    if  _comment != None:
        _comment = textwrap.fill(_comment, width=70).split("\n")
        #print(">>>", len(_comment))
        for i in _comment:
            _tmp += f"  ## {i}\n"
    return _tmp

def get_constructor(data):
    _params = export_params(data["params"])   
    _tmp = ""
    if _params != "":
        _tmp = "(@)"
    _tmp = f'proc constructor_{data["name"]}*({_params}): {data["class_name"]} {{.constructor,importcpp: "{data["name"]}{_tmp}".}}\n'
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
        _return = f': {_result}'

    _tmp = f'proc {data["name"]}*({_params}){_return}  {{.importcpp: "{data["name"]}".}}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp



def get_typedef(data, include = None):   # TODO: añadir opción si no está referenciado, comentar
    #for i in data:
        #if i["name"] in _types:
    _type = get_nim_type( data["underlying"] )
    _include = ""
    if include != None:
        _include = f'include: "{include}", '
    return f'  {data["name"]}* {{.{_include}importcpp: "{data["name"]}".}} = {_type}\n'
    #_data[_file]["typedefs"].append((i["name"], _type))

def get_class(data, include = None, byref = True):
    #pprint(data)
    _name = data["name"]
    _include = ""
    if include != None:
        _include = f'include: "{include}", '
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
                elif item[1] == "method":
                    _methods.append(get_method(item[2]))
                    #_classes.append(get_class(item[2], _tmpFile))
                elif item[1] == "typedef":
                    _typedefs.append( get_typedef(item[2], _tmpFile))
                elif item[1] == "class":
                    _classes.append(get_class(item[2], _tmpFile))
        #_classes = list(set(_classes))  
        #print(_classes)
                
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

    #_root, _dirs, _files = list(os.walk(_folder))[0]
    #_files = [i for i in _files if ".hxx" in i]  # Remove the .lxx files
    #_files = [i for i in _files if "gp_" == i[0:3]]
    #print(_folder)
    _root = get_root(_folder)    
    _files = glob.glob(_folder, recursive = True)

    print("Root folder: ", _root)

    #for root, dirs, files in os.walk(_folder): 
    _fname = os.path.join(_dest,_dest) + ".nim"
    _fp1 = open(_fname, "w")
    _fp1.write('{.passL: "-lTKBO -lTKSTEP -lTKPrim -lTKSTEPAttr -lTKSTEP209 -lTKSTEPBase -lTKXSBase -lTKShHealing -lTKTopAlgo -lTKGeomAlgo -lTKBRep -lTKGeomBase -lTKG3d -lTKG2d -lTKMath -lTKernel", passC:"-I/usr/include/opencascade" .}\n\n')
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
                #print("\n\n")
                #print(node.spelling, ">>>", node.kind)
                #print("displayname: ",node.displayname)
                #for i in node.get_arguments():
                #    print("  argument>",i)
                #pprint(dir(node))
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
                
                #pprint(dir(node))
                #print(node.result_type.spelling)
                _data = {"name" : _name}
                _data["result"] = node.result_type.spelling
                _data["class_name"] = node.semantic_parent.spelling
                _data["const_method"] = node.is_const_method()
                #-----
                #if _name == "SetX":
                    #print(dir(node))
                #    print(dir(node.result_type))
                #    print(node.spelling)
                #    print(node.result_type.spelling)
                #    print(node.result_type.is_const_qualified())
                #    print(node.is_const_method())
                    #print(node.result_type.)
                #-----
                #_data["sourcefile"] = node.location.file.name
                _params = []
                for i in node.get_children():
                    if i.kind == clang.cindex.CursorKind.PARM_DECL:
                        _paramName = i.displayname
                        _params.append((i.displayname, i.type.spelling))
                _data["params"] = _params
                _data["comment"] = node.brief_comment
                #_methods.append( _data)
                _all.append(( node.location.file.name, "method", _data ))


            # Classes
            if node.kind == clang.cindex.CursorKind.CLASS_DECL and node.is_definition():
            #if node.spelling == "gp_Trsf2d":
                _data = { "name" : node.spelling,
                          "comment": node.brief_comment }
                          #"kind": node.kind }
                #if "Defines a non-persistent transformation" in _data["comment"]:
                #print( dir(node) )
                
                #pprint(_data)
                #print(node.is_definition())
                _all.append(( node.location.file.name, "class", _data ))
                

            # Types
            # Methods
            if node.kind == clang.cindex.CursorKind.TYPEDEF_DECL:
                _data = { "name" : node.displayname,
                            "underlying": node.underlying_typedef_type.spelling }          
                _all.append(( node.location.file.name, "typedef", _data ))

        # Only consider data associated to the file itself
        _all = [i for i in _all if i[0] == include_file]

        export_per_file( _all, files = [include_file], 
                         output=_dest,
                         filter=_root)

    _fp1 = open(_fname, "a+")
    for _file in _files:
        _fname = _file.split(_root)[1]
        _fp1.write(f'include "{_fname}"\n')
    _fp1.close()            

# TODO: when to add "var " like "this: var gp_Pnt". 
# - Cuando devuelve "void"?



"""
//! For this point, assigns  the values Xp, Yp and Zp to its three coordinates.
void SetCoord (const Standard_Real Xp, const Standard_Real Yp, const Standard_Real Zp);

proc SetCoord*(this: var gp_Pnt; Index: Standard_Integer; Xi: Standard_Real) {.
    importcpp: "SetCoord", header: "gp_Pnt.hxx".}

        {
          "id": "0x55f8bd65bc28",
          "kind": "CXXMethodDecl",
          "isUsed": true,
          "name": "SetCoord",
          "mangledName": "_ZN6gp_XYZ8SetCoordEddd",
          "type": {
            "qualType": "void (const Standard_Real, const Standard_Real, const Standard_Real)"
          },
          "inner": [
            {
              "id": "0x55f8bd65ba98",
              "kind": "ParmVarDecl",
              "name": "X",
              "mangledName": "_ZZN6gp_XYZ8SetCoordEdddE1X",
              "type": {
                "desugaredQualType": "const double",
                "qualType": "const Standard_Real",
                "typeAliasDeclId": "0x55f8bc7ad080"
              }
            },
            {
              "id": "0x55f8bd65bb10",
              "kind": "ParmVarDecl",
              "name": "Y",
              "mangledName": "_ZZN6gp_XYZ8SetCoordEdddE1Y",
              "type": {
                "desugaredQualType": "const double",
                "qualType": "const Standard_Real",
                "typeAliasDeclId": "0x55f8bc7ad080"
              }
            },
            {
              "id": "0x55f8bd65bb88",
              "kind": "ParmVarDecl",
              "name": "Z",
              "mangledName": "_ZZN6gp_XYZ8SetCoordEdddE1Z",
              "type": {
                "desugaredQualType": "const double",
                "qualType": "const Standard_Real",
                "typeAliasDeclId": "0x55f8bc7ad080"
              }
            },


"""

"""
    void SetCoord (const Standard_Integer Index, const Standard_Real Xi);
  

  
  //! Assigns the given value to the X coordinate of this point.
    void SetX (const Standard_Real X);
  
  //! Assigns the given value to the Y coordinate of this point.
    void SetY (const Standard_Real Y);
  
  //! Assigns the given value to the Z coordinate of this point.
    void SetZ (const Standard_Real Z);
  
  //! Assigns the three coordinates of Coord to this point.
    void SetXYZ (const gp_XYZ& Coord);
  

  //! Returns the coordinate of corresponding to the value of  Index :
  //! Index = 1 => X is returned
  //! Index = 2 => Y is returned
  //! Index = 3 => Z is returned
  //! Raises OutOfRange if Index != {1, 2, 3}.
  //! Raised if Index != {1, 2, 3}.
    Standard_Real Coord (const Standard_Integer Index) const;
  
  //! For this point gives its three coordinates Xp, Yp and Zp.
    void Coord (Standard_Real& Xp, Standard_Real& Yp, Standard_Real& Zp) const;
  
  //! For this point, returns its X coordinate.
    Standard_Real X() const;
  





void SetX (const Standard_Real X);

proc SetX*(this: var gp_Pnt; X: Standard_Real) {.importcpp: "SetX", header: "gp_Pnt.hxx".}



proc SetXYZ*(this: var gp_Pnt; Coord: gp_XYZ) {.importcpp: "SetXYZ",
    header: "gp_Pnt.hxx".}





#----------
Standard_Real Coord (const Standard_Integer Index) const;

proc Coord*(this: gp_Pnt; Index: Standard_Integer): Standard_Real {.noSideEffect,
    importcpp: "Coord", header: "gp_Pnt.hxx".}


#-------

  
//! For this point gives its three coordinates Xp, Yp and Zp.
void Coord (Standard_Real& Xp, Standard_Real& Yp, Standard_Real& Zp) const;

proc Coord*(this: gp_Pnt; Xp: var Standard_Real; Yp: var Standard_Real;
           Zp: var Standard_Real) {.noSideEffect, importcpp: "Coord",
                                 header: "gp_Pnt.hxx".}

"""

"""
[ 'access_specifier', 'availability', 'brief_comment', 'canonical', 'data', 'displayname',
 'enum_type', 'enum_value', 'exception_specification_kind', 'extent', 'from_cursor_result',
 'from_location', 'from_result', 'get_arguments', 'get_bitfield_width', 'get_children',
 'get_definition', 'get_field_offsetof', 'get_included_file', 'get_num_template_arguments', 
 'get_template_argument_kind', 'get_template_argument_type', 
 'get_template_argument_unsigned_value', 'get_template_argument_value', 'get_tokens', 
 'get_usr', 'hash', 'is_abstract_record', 'is_anonymous', 'is_bitfield', 'is_const_method', 
 'is_converting_constructor', 'is_copy_constructor', 'is_default_constructor', 
 'is_default_method', 'is_definition', 'is_move_constructor', 'is_mutable_field', 
 'is_pure_virtual_method', 'is_scoped_enum', 'is_static_method', 'is_virtual_method', 'kind', 
 'lexical_parent', 'linkage', 'location', 'mangled_name', 'objc_type_encoding', 'raw_comment', 
 'referenced', 'result_type', 'semantic_parent', 'spelling', 'storage_class', 'tls_kind', 
 'translation_unit', 'type', 'underlying_typedef_type', 'walk_preorder', 'xdata']

['argument_types', 'data', 'element_count', 'element_type', 'from_result', 'get_address_space', 
'get_align', 'get_array_element_type', 'get_array_size', 'get_canonical', 'get_class_type', 
'get_declaration', 'get_exception_specification_kind', 'get_fields', 'get_named_type', 
'get_num_template_arguments', 'get_offset', 'get_pointee', 'get_ref_qualifier', 'get_result', 
'get_size', 'get_template_argument_type', 'get_typedef_name', 'is_const_qualified', 
'is_function_variadic', 'is_pod', 'is_restrict_qualified', 'is_volatile_qualified', 'kind', 
'spelling', 'translation_unit']

"""
