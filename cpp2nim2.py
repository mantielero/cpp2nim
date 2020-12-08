#!/usr/bin/env python
""" Usage: call with <filename> <typename>
$ python cpp2nim.py /usr/include/opencascade occt

>>> import clang.cindex
>>> index = clang.cindex.Index.create()
>>> tu = index.parse("/usr/include/opencascade/gp_Pnt.hxx", ['-x', 'c++',  "-I/usr/include/opencascade"], None, clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)

clang -Xclang -ast-dump -fno-diagnostics-color miniz.c

|-TypedefDecl 0x55a1bf4a56f8 <line:1079:1, line:1097:3> col:3 referenced mz_zip_reader_extract_iter_state 'struct mz_zip_reader_extract_iter_state':'mz_zip_reader_extract_iter_state'
| `-ElaboratedType 0x55a

http://szelei.me/code-generator/

https://pypi.org/project/pcpp/
"""

import sys
import clang.cindex
import string
import os
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
    if c_type[0:5] == "const":
        c_type = c_type[5:].strip()
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
        #print(p)
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
        _tmp += f"  ## {_comment}"
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
    #pprint(data)
    _params = export_params(data["params"])
    if _params != "":
        _params = ", " + _params
    _params = f'this: {data["class_name"]}' + _params
    
    _return = ""
    if data["result"] not in ["void", "void *"]:
        _return = f': {data["result"]}'
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

def get_class(data, include = None):
    _name = data["class_name"]
    _include = ""
    if include != None:
        _include = f'include: "{include}", '    
    _tmp = f'  {_name}* {{.{_include}importcpp: "{_name}", byref.}} = object\n'
    _tmp += get_comment(data) + "\n "
    return _tmp    


def export_per_file(data, files = [], output= "occt", filter=None):
    _fname = os.path.join(output,output) + ".nim"
    _fp1 = open(_fname, "a+")
    #_fp1.write('{.passL: "-lTKG2d -lTKernel", passC:"-I/usr/include/opencascade" }\n\n')

    _newfiles = []
    for _file in files:
        _typedefs     = []
        _constructors = []
        _methods      = []
        _classes      = []
        for item in data:
            if _file in item[0]:
                _tmpFile = _file.split(filter)[1]
                if item[1] == "constructor":
                    _constructors.append(get_constructor(item[2]))
                    _classes.append(get_class(item[2], _tmpFile))
                elif item[1] == "method":
                    _methods.append(get_method(item[2]))
                    _classes.append(get_class(item[2], _tmpFile))
                elif item[1] == "typedef":
                    _typedefs.append( get_typedef(item[2], _tmpFile))
        _classes = list(set(_classes))  
        #print(_classes)  
                
        _fname = ""
        _popfile = None
        if filter != None:
            _fname = _file.split(_folder)[1]
            _popfile = _fname
        _fname = os.path.splitext(_fname)[0]
        _nimname = _fname + ".nim"
        _newfiles.append( _nimname)        
        _fname = os.path.join(output, _nimname)

        if len(_typedefs) > 0 or len(_classes) > 0:
            #_fp1.write(f'{{.push header: "{_popfile}".}}\n')
            #_fp1.write("type\n")
            for _i in _typedefs:
                _fp1.write(_i)
            for _i in _classes:
                _fp1.write(_i)                
            #_fp1.write(f'{{.pop.}} # header: "{_popfile}\n')

        if len(_constructors) > 1 or len(_methods) > 1:
            _fp = open(_fname, "w")
            _fp.write(f'{{.push header: "{_popfile}".}}\n')        
            _fp.write("\n\n# Constructors and methods\n")
            for _i in _constructors:
                _fp.write(_i)
            for _i in _methods:
                _fp.write(_i)        
            _fp.write(f'{{.pop.}} # header: "{_popfile}\n')
            _fp.close()


    for _file in _newfiles:
        _fp1.write(f'include "{_file}"\n')
    _fp1.close()



if __name__ == '__main__':
    _folder = sys.argv[1]
    _dest = sys.argv[2]
    _path = os.getcwd()
    _destination_folder = os.path.join(_path, _dest)
    try:
        os.mkdir(_destination_folder)
    except:
        pass

    _root, _dirs, _files = list(os.walk(_folder))[0]
    _files = [i for i in _files if ".hxx" in i]  # Remove the .lxx files
    _files = [i for i in _files if "gp_" == i[0:3]]

    #for root, dirs, files in os.walk(_folder): 
    for include_file in _files:
            index = clang.cindex.Index.create()
            args = ['-x', 'c++',  f"-I{_folder}"]  # "-Wall", '-std=c++11', '-D__CODE_GENERATOR__'
            #opts = TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES # a bitwise or of TranslationUnit.PARSE_XXX flags.
            opts = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
            fname = os.path.join(_root,include_file)
            tu = index.parse(fname, args, None, opts)

            #_folder = "/usr/include/opencascade/"    
            _all = []
            #_constructors = []
            _methods = []
            _typedefs = []
            for depth,node in get_nodes( tu.cursor, depth=0 ):  # Traverses the whole tree
                _node = {}
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
                    _data = {"name" : node.spelling}
                    _data["result"] = node.result_type.spelling
                    _data["class_name"] = node.semantic_parent.spelling
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

                # Types
                # Methods
                if node.kind == clang.cindex.CursorKind.TYPEDEF_DECL:
                    _data = { "name" : node.displayname,
                                "underlying": node.underlying_typedef_type.spelling }          
                    _all.append(( node.location.file.name, "typedef", _data ))

            #-----------
            #   pprint(_all)
            #print( yaml.dump(_all) )
            #-----------
            # Only the files in: /usr/include/opencascade
            _files = list(set( [i[0] for i in _all if fname in i[0]] ))

            print(_files)
            _fname = os.path.join(_dest,_dest) + ".nim"
            _fp1 = open(_fname, "w")
            _fp1.write('{.passL: "-lTKBO -lTKSTEP -lTKPrim -lTKSTEPAttr -lTKSTEP209 -lTKSTEPBase -lTKXSBase -lTKShHealing -lTKTopAlgo -lTKGeomAlgo -lTKBRep -lTKGeomBase -lTKG3d -lTKG2d -lTKMath -lTKernel", passC:"-I/usr/include/opencascade" .}\n\n')
            _fp1.write("type\n")            
            _fp1.close()            
            export_per_file( _all, files = _files, 
                             output=_dest,
                             filter=_folder)
            

