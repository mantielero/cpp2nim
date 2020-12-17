# cpp2nim
Create bindings to C++ projects (Warning - far from complete but might be useful)

It just looks for methods and constructors and wraps them (it even does it right in some cases!). It also puts the types in the project


# How to use it
You can use it as follows:
- Process a whole folder: the following example will look for all the files within `/usr/include/opencascade` and create a `.nim` for every occurance. All those files will be stored under `occt` folder. It will create also a `occt/occt.nim` file including all those other files and wrapping some objects and types.
```
python cpp2nim.py "/usr/include/opencascade/*.hxx" occt
```
- Process some of the files: the following will do the same for the files meeting the glob: `gp_*.hxx`. This is useful for very big libraries like OpenCascade (>8000 header files).
```
python cpp2nim.py "/usr/include/opencascade/gp_*.hxx" occt
```
- One file: the following will also work
```
python cpp2nim.py "/usr/include/opencascade/gp_Pnt.hxx" occt
```

And for OpenSceneGraph:
```
$ python cpp2nim.py "/usr/include/osg/*" osg
$ python cpp2nim.py "/usr/include/osgViewer/**/*" osg
```

> Provided that those libraries are installed on your system. (only tested on linux)

I recommend to adapt it to your own needs. I think it can give a good start.

# ToDo
- There is a lot of missing stuff. 
- Spaguetty code
- PassL, PassC
- I don't know C++ (just the very basic)


