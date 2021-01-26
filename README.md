# cpp2nim
Used to make easier the creation of bindings to C++ projects (Warning - far from complete but might be useful)



# How to use it
It works in two stages:
## Parsing
This is the slowest step. This is done as follows:

- Process a whole folder: the following example will look for all the files within `/usr/include/opencascade`. 
```
python parse_headers.py "/usr/include/opencascade/*.hxx" occt
```
- Process some of the files: the following will do the same for the files meeting the glob: `gp_*.hxx`. This is useful for very big libraries like OpenCascade (>8000 header files).
```
python parse_headers.py "/usr/include/opencascade/gp_*.hxx" occt
```
- One file: the following will also work
```
python parse_headers.py "/usr/include/opencascade/gp_Pnt.hxx" occt
```

And for OpenSceneGraph:
```
$ python parse_headers.py "/usr/include/osg/*" osg
$ python parse_headers.py "/usr/include/osgViewer/**/*" osg
```

> Provided that those libraries are installed on your system. (only tested on linux)

The execution will create the folder writen in the second parameter (`occt` or `osg` in the prior examples). Within them the file `deleteme/files.pickle` will be created with the result from the parsing. It should be easy to export it to `yaml` or `json` and process it directly with nim.

## Bindings generation
To create the bindings, you just need to do something like:
```
$ python analyse.py osg
```
This will:
1. Read the file `osg/deleteme/files.pickle`
2. Create a `<header>.nim` file per header.
3. Create a `osg_types.nim` file with shared types across different headers.
4. Create a `osg.nim` which imports all the other headers.

# Conclusion
The result most likel won't work, but hopefully will get you closer to the result. 

I recommend to adapt it to your own needs. 

I hope somebody make something better than this. ;oP

# ToDo
- There is a lot of missing stuff. 
- Spaguetty code
- PassL, PassC
- I don't know C++ (just the very basic)


