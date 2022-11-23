# Deep In Python
[toc]

---

## 引言

运行一个程序时，python 做了哪些事情？

```
python app.py
```

## python 语言定义与实现

---


##### python 定义

与 C 语言不同，python 没有官方标准，最接近官方标准的文档是所谓的 python 语言参考手册（Python Language Reference），
而 python 语言参考手册的开头是这么说的：

    我希望尽可能地保证内容精确无误，但还是选择使用自然语言而不是正式的标准说明进行描述，正式的标准说明仅用于句法和词法解析部分。
    这样应该能使这份文档对于普通人来说更容易理解，但也可能导致一些歧义。
    因此，如果你来自火星并且想凭借这份文档把 Python 重新实现一遍，有时也许需要自行猜测，实际上最终大概会得到一个十分不同的语言。
    而在另一方面，如果你正在使用 Python 并且想了解有关该语言特定领域的精确规则，你应该能够在这里找到它们。


##### python 实现
    CPython, PyPy、Jython、IronPython, ...


## Python 程序运行

---

#### 执行流程分为 3 个阶段：

1. 初始化
   
   CPython 会初始化 Python 运行所需的各种数据结构，准备内建类型、配置信息，加载内建模块，建立依赖系统，并完成很多其它必要的准备工作。
   
2. 编译阶段
   
   解析源码，建立 AST（Abstract Syntax Tree 抽象语法树），根据 AST 生成字节码，并对字节码做一些可能的优化。
   
3. 解释阶段
   
   CPython 的核心虚拟机执行字节码，整个字节码的执行过程被包含在一个巨大的求值循环（evaluation loop）中，
   只要还有可执行指令，就会一直执行，直到最终返回一个值，或者遇到某种错误。

   
#### 代码执行流程：
```
# Windows
python.c--wmain
# Not Windows
python.c--main

  # Windows
  main.c--Py_Main
  # Not Windows
  main.c--Py_BytesMain

    main.c--pymain_main

      main.c--pymain_init

      main.c--Py_RunMain

        main.c--pymain_run_python

          # Run pyc file or source code file, or run REPL mode loop.
          main.c--pymain_run_filename

            # Run pyc file or source code file, or run REPL mode loop.
            pythonrun.c--PyRun_AnyFileExFlags

              # Run pyc file or source code file, or print error.
              pythonrun.c--PyRun_SimpleFileExFlags

                # Run source code file.
                pythonrun.c--PyRun_FileExFlags

                  # Compile file to AST node.
                  pythonrun.c--PyParser_ASTFromFileObject

                    # Compile file to CST.
                    parsetok.c--PyParser_ParseFileObject

                      # Create tokenizer.
                      tokenizer.c--PyTokenizer_FromFile

                      # Compile string to CST.
                      parsetok.c--parsetok

                        # Create parser state.
                        parser.c--PyParser_New

                        # Transit DFA and create CST nodes.
                        parser.c--PyParser_AddToken

                    # Convert CST to AST node.
                    ast.c--PyAST_FromNodeObject

                  # Compile AST node to code object and run.
                  pythonrun.c--run_mod

                    # Compile AST node to code object.
                    compile.c--PyAST_CompileObject

                    # Run code object.
                    pythonrun.c--run_eval_code_obj

                      ceval.c--PyEval_EvalCode

                        ceval.c--PyEval_EvalCodeEx

                          ceval.c--_PyEval_EvalCodeWithName

                            ceval.c--PyEval_EvalFrameEx

                              ceval.c--_PyEval_EvalFrameDefault
```


#### 程序执行入口

正如所有 C 程序一样，CPython 的执行入口是 Programs/python.c 中的一个 [main()](https://github.com/python/cpython/blob/3.8/Programs/python.c) 函数：
```
/* Minimal main program -- everything is loaded from the library */

#include "Python.h"
#include "pycore_pylifecycle.h"

#ifdef MS_WINDOWS
int
wmain(int argc, wchar_t **argv)
{
    return Py_Main(argc, argv);
}
#else
int
main(int argc, char **argv)
{
    return Py_BytesMain(argc, argv);
}
#endif
```

在 Windows 系统中，为接收 UTF-16 编码的字符串参数，CPython 使用 wmain() 函数作为入口。
而在其它平台上，CPython 需要额外执行一个步骤，将 char 字符串转为 wchar_t 字符串，
char 字符串的编码方式取决于 locale 设置，而 wchar_t 的编码方式则取决于 wchar_t 的长度。
例如，如果 sizeof(wchar_t) 为 4，则采用 UCS-4 编码。

Py_Main 和Py_BytesMain 在文件 [Modules/main.c](https://github.com/python/cpython/blob/3.8/Modules/main.c#L724) 中, 
以不同参数调用了 [pymain_main()](https://github.com/python/cpython/blob/3.8/Modules/main.c#L707)
```
int
Py_Main(int argc, wchar_t **argv)
{
    _PyArgv args = {
        .argc = argc,
        .use_bytes_argv = 0,
        .bytes_argv = NULL,
        .wchar_argv = argv};
    return pymain_main(&args);
}


int
Py_BytesMain(int argc, char **argv)
{
    _PyArgv args = {
        .argc = argc,
        .use_bytes_argv = 1,
        .bytes_argv = argv,
        .wchar_argv = NULL};
    return pymain_main(&args);
}
```
```
static int
pymain_main(_PyArgv *args)
{
    PyStatus status = pymain_init(args);
    if (_PyStatus_IS_EXIT(status)) {
        pymain_free();
        return status.exitcode;
    }
    if (_PyStatus_EXCEPTION(status)) {
        pymain_exit_error(status);
    }

    return Py_RunMain();
}
```

pymain_main() 首先调用 pymain_init() 执行初始化，然后调用 Py_RunMain() 进行下一步工作。

### 一. 初始化

文件 Modules/main.c 函数 [pymain_init](https://github.com/python/cpython/blob/3.8/Modules/main.c#L36) 执行初始化。
```
static PyStatus
pymain_init(const _PyArgv *args)
{
    PyStatus status;

    // 初始化运行时状态
    status = _PyRuntime_Initialize();
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }

    // 初始化默认配置
    PyPreConfig preconfig;
    PyPreConfig_InitPythonConfig(&preconfig);
    
    // 预初始化
    status = _Py_PreInitializeFromPyArgv(&preconfig, args);
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }
    // 预初始化完成，为下一个初始化阶段准备参数

    // 初始化默认配置
    PyConfig config;
    PyConfig_InitPythonConfig(&config);

    // 将命令行参数存储至 `config->argv`
    /* pass NULL as the config: config is read from command line arguments,
       environment variables, configuration files */
    if (args->use_bytes_argv) {
        status = PyConfig_SetBytesArgv(&config, args->argc, args->bytes_argv);
    }
    else {
        status = PyConfig_SetArgv(&config, args->argc, args->wchar_argv);
    }
    if (_PyStatus_EXCEPTION(status)) {
        goto done;
    }

    // 执行核心初始化和主初始化
    status = Py_InitializeFromConfig(&config);
    if (_PyStatus_EXCEPTION(status)) {
        goto done;
    }
    status = _PyStatus_OK();

done:
    PyConfig_Clear(&config);
    return status;
}
```

1. 预初始化（preinitialization）--准备默认的内存分配器，完成基本配置
2. 核心初始化（core initialization）--核心初始化阶段负责初始化解释器状态、主线程状态、内置类型与异常、内置模块，准备 sys 模块与模块导入系统
3. 主初始化（main initialization）--初始化剩余


#### 预初始化
[_PyRuntime_Initialize()](https://github.com/python/cpython/blob/3.8/Python/pylifecycle.c#L74) 负责初始化运行时状态，运行时状态存储在 _PyRuntime 全局变量中, 其结构体定义在
[_PyRuntimeState](https://github.com/python/cpython/blob/3.8/Include/internal/pycore_pystate.h#L195) 。

_Py_PreInitializeFromPyArgv() 负责读取命令行参数、环境变量以及全局配置，并完成 _PyRuntime.preconfig、本地化以及内存分配器设置。
它只读取和预初始化相关的参数，例如，命令行参数中的 -E -I -X 等。

下一步准备初始化需要的配置 [PyConfig](https://github.com/python/cpython/blob/3.8/Include/cpython/initconfig.h#L129) 。 
这里的配置保存着绝大多数 Python 相关配置，在整个初始化、以及 Python 程序执行过程中使用广泛。

调用 PyConfig_InitPythonConfig() 创建默认配置，
然后调用 PyConfig_SetBytesArgv() 将命令行参数存储至 config.argv 中，
最后调用 Py_InitializeFromConfig() 执行核心初始化和主初始化。

下面，我们来看看 [Py_InitializeFromConfig()](https://github.com/python/cpython/blob/3.8/Python/pylifecycle.c#L1015) ：
```
PyStatus
Py_InitializeFromConfig(const PyConfig *config)
{
    if (config == NULL) {
        return _PyStatus_ERR("initialization config is NULL");
    }

    PyStatus status;

    status = _PyRuntime_Initialize();
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }
    _PyRuntimeState *runtime = &_PyRuntime;

    PyInterpreterState *interp = NULL;
    // 核心初始化阶段
    status = pyinit_core(runtime, config, &interp);
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }
    config = &interp->config;

    if (config->_init_main) {
         // 主初始化阶段
        status = pyinit_main(runtime, interp);
        if (_PyStatus_EXCEPTION(status)) {
            return status;
        }
    }

    return _PyStatus_OK();
}
```


#### 核心初始化

核心初始化由 [pyinit_core()](https://github.com/python/cpython/blob/3.8/Python/pylifecycle.c#L832) 完成。 具体可以分为两步：
1. 准备相关配置：解析命令行参数，读取环境变量，确定文件路径，选择标准流与文件系统的编码方式，并将这些数据写入配置变量的对应位置；
2. 应用这些配置：设置标准流，生成哈希函数密钥，创建主解释器状态与主线程状态，初始化 GIL 并占用，使能垃圾收集器，初始化内置类型与异常，
   初始化 sys 模块及内置模块，为内置模块与冻结模块准备好模块导入系统
   
其中第二步由 pyinit_core -- [pyinit_config()](https://github.com/python/cpython/blob/3.8/Python/pylifecycle.c#L660) 完成。
```
static PyStatus
pyinit_config(_PyRuntimeState *runtime,
              PyInterpreterState **interp_p,
              const PyConfig *config)
{
    PyInterpreterState *interp;

    _PyConfig_Write(config, runtime);

    // 根据配置设置 Py_* 全局变量
    // 初始化标准流（stdin, stdout, stderr）
    // 为哈希函数设置密钥
    PyStatus status = pycore_init_runtime(runtime, config);
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }

    // 创建主解释器状态和主线程状态
    // 占用 GIL
    status = pycore_create_interpreter(runtime, config, &interp);
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }
    config = &interp->config;
    *interp_p = interp;
    
    // 以下为初始化数据类型、异常、sys、内置函数和模块、导入系统等
    
    // 初始化数据类型
    status = pycore_init_types();
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }

    PyObject *sysmod;
    status = _PySys_Create(runtime, interp, &sysmod);
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }

    status = pycore_init_builtins(interp);
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }

    status = pycore_init_import_warnings(interp, sysmod);
    if (_PyStatus_EXCEPTION(status)) {
        return status;
    }

    /* Only when we get here is the runtime core fully initialized */
    runtime->core_initialized = 1;
    return _PyStatus_OK();
}
```

pycore_init_types() 函数负责初始化内置类型。具体做了哪些事情呢？内置类型又是什么？

我们知道，Python 中一切皆对象。数字、字符串、列表、函数、模块、帧、自定义类乃至内置类型都是 Python 对象。
所有 Python 对象都是 PyObject 结构或以 PyObject 作为第一个字段的其它 C 结构的一个实例。
PyObject 有两个字段，第一个是 Py_ssize_t 类型的引用计数，第二个是 PyTypeObject 指针，指向对象类型。
下面是 PyObject 结构体的定义：

Python 对象基石 [PyObject](https://github.com/python/cpython/blob/3.8/Include/object.h#L104)
```
typedef struct _object {
    _PyObject_HEAD_EXTRA
    Py_ssize_t ob_refcnt;
    struct _typeobject *ob_type;
} PyObject;
```

下面是 [PyFloatObject](https://github.com/python/cpython/blob/3.8/Include/floatobject.h#L15) 类型结构体定义
```
typedef struct {
    PyObject_HEAD // 一个宏，#define PyObject_HEAD PyObject ob_base;
    double ob_fval;
} PyFloatObject;
```

[python 类型](https://github.com/python/cpython/blob/3.8/Include/cpython/object.h#L177)
```
typedef struct _typeobject {
    PyObject_VAR_HEAD
    const char *tp_name; /* For printing, in format "<module>.<name>" */
    Py_ssize_t tp_basicsize, tp_itemsize; /* For allocation */

    /* Methods to implement standard operations */

    destructor tp_dealloc;
    Py_ssize_t tp_vectorcall_offset;
    getattrfunc tp_getattr;
    setattrfunc tp_setattr;
    PyAsyncMethods *tp_as_async; /* formerly known as tp_compare (Python 2)
                                    or tp_reserved (Python 3) */
    reprfunc tp_repr;

    /* Method suites for standard classes */

    PyNumberMethods *tp_as_number;
    PySequenceMethods *tp_as_sequence;
    PyMappingMethods *tp_as_mapping;

    /* More standard operations (here for binary compatibility) */

    hashfunc tp_hash;
    ternaryfunc tp_call;
    reprfunc tp_str;
    getattrofunc tp_getattro;
    setattrofunc tp_setattro;

    /* Functions to access object as input/output buffer */
    PyBufferProcs *tp_as_buffer;

    /* Flags to define presence of optional/expanded features */
    unsigned long tp_flags;

    const char *tp_doc; /* Documentation string */

    /* Assigned meaning in release 2.0 */
    /* call function for all accessible objects */
    traverseproc tp_traverse;

    /* delete references to contained objects */
    inquiry tp_clear;

    /* Assigned meaning in release 2.1 */
    /* rich comparisons */
    richcmpfunc tp_richcompare;

    /* weak reference enabler */
    Py_ssize_t tp_weaklistoffset;

    /* Iterators */
    getiterfunc tp_iter;
    iternextfunc tp_iternext;

    /* Attribute descriptor and subclassing stuff */
    struct PyMethodDef *tp_methods;
    struct PyMemberDef *tp_members;
    struct PyGetSetDef *tp_getset;
    struct _typeobject *tp_base;
    PyObject *tp_dict;
    descrgetfunc tp_descr_get;
    descrsetfunc tp_descr_set;
    Py_ssize_t tp_dictoffset;
    initproc tp_init;
    allocfunc tp_alloc;
    newfunc tp_new;
    freefunc tp_free; /* Low-level free-memory routine */
    inquiry tp_is_gc; /* For PyObject_IS_GC */
    PyObject *tp_bases;
    PyObject *tp_mro; /* method resolution order */
    PyObject *tp_cache;
    PyObject *tp_subclasses;
    PyObject *tp_weaklist;
    destructor tp_del;

    /* Type attribute cache version tag. Added in version 2.6 */
    unsigned int tp_version_tag;

    destructor tp_finalize;
    vectorcallfunc tp_vectorcall;

    /* bpo-37250: kept for backwards compatibility in CPython 3.8 only */
    Py_DEPRECATED(3.8) int (*tp_print)(PyObject *, FILE *, int);

#ifdef COUNT_ALLOCS
    /* these must be last and never explicitly initialized */
    Py_ssize_t tp_allocs;
    Py_ssize_t tp_frees;
    Py_ssize_t tp_maxalloc;
    struct _typeobject *tp_prev;
    struct _typeobject *tp_next;
#endif
} PyTypeObject;
```


内置类型，如 float, int、list 等，是通过静态声明 PyTypeObject 实例实现的， 
如 [PyFloat_Type](https://github.com/python/cpython/blob/3.8/Objects/floatobject.c#L1882) ：
```
PyTypeObject PyFloat_Type = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "float",
    sizeof(PyFloatObject),
    0,
    (destructor)float_dealloc,                  /* tp_dealloc */
    0,                                          /* tp_vectorcall_offset */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_as_async */
    (reprfunc)float_repr,                       /* tp_repr */
    &float_as_number,                           /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    (hashfunc)float_hash,                       /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,   /* tp_flags */
    float_new__doc__,                           /* tp_doc */
    0,                                          /* tp_traverse */
    0,                                          /* tp_clear */
    float_richcompare,                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    0,                                          /* tp_iter */
    0,                                          /* tp_iternext */
    float_methods,                              /* tp_methods */
    0,                                          /* tp_members */
    float_getset,                               /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    0,                                          /* tp_init */
    0,                                          /* tp_alloc */
    float_new,                                  /* tp_new */
};
```

类型声明之后，需要进行初始化。比如，将 __call__、__eq__ 等方法添加到该类型对应的字典中，并指向相应的 tp_* 函数。
这个初始化过程是通过调用 [PyType_Ready()](https://github.com/python/cpython/blob/3.8/Objects/typeobjects.c#L5235) 函数完成的：

```
PyStatus
_PyTypes_Init(void)
{
#define INIT_TYPE(TYPE, NAME) \
    do { \
        if (PyType_Ready(TYPE) < 0) { \
            return _PyStatus_ERR("Can't initialize " NAME " type"); \
        } \
    } while (0)

    INIT_TYPE(&PyBaseObject_Type, "object");
    INIT_TYPE(&PyType_Type, "type");
    INIT_TYPE(&_PyWeakref_RefType, "weakref");
    INIT_TYPE(&_PyWeakref_CallableProxyType, "callable weakref proxy");
    INIT_TYPE(&_PyWeakref_ProxyType, "weakref proxy");
    INIT_TYPE(&PyLong_Type, "int");
    INIT_TYPE(&PyBool_Type, "bool");
    INIT_TYPE(&PyByteArray_Type, "bytearray");
    INIT_TYPE(&PyBytes_Type, "str");
    INIT_TYPE(&PyList_Type, "list");
    INIT_TYPE(&_PyNone_Type, "None");
    INIT_TYPE(&_PyNotImplemented_Type, "NotImplemented");
    INIT_TYPE(&PyTraceBack_Type, "traceback");
    INIT_TYPE(&PySuper_Type, "super");
    INIT_TYPE(&PyRange_Type, "range");
    INIT_TYPE(&PyDict_Type, "dict");
    INIT_TYPE(&PyDictKeys_Type, "dict keys");
    INIT_TYPE(&PyDictValues_Type, "dict values");
    INIT_TYPE(&PyDictItems_Type, "dict items");
    INIT_TYPE(&PyDictRevIterKey_Type, "reversed dict keys");
    INIT_TYPE(&PyDictRevIterValue_Type, "reversed dict values");
    INIT_TYPE(&PyDictRevIterItem_Type, "reversed dict items");
    INIT_TYPE(&PyODict_Type, "OrderedDict");
    INIT_TYPE(&PyODictKeys_Type, "odict_keys");
    INIT_TYPE(&PyODictItems_Type, "odict_items");
    INIT_TYPE(&PyODictValues_Type, "odict_values");
    INIT_TYPE(&PyODictIter_Type, "odict_keyiterator");
    INIT_TYPE(&PySet_Type, "set");
    INIT_TYPE(&PyUnicode_Type, "str");
    INIT_TYPE(&PySlice_Type, "slice");
    INIT_TYPE(&PyStaticMethod_Type, "static method");
    INIT_TYPE(&PyComplex_Type, "complex");
    INIT_TYPE(&PyFloat_Type, "float");
    INIT_TYPE(&PyFrozenSet_Type, "frozenset");
    INIT_TYPE(&PyProperty_Type, "property");
    INIT_TYPE(&_PyManagedBuffer_Type, "managed buffer");
    INIT_TYPE(&PyMemoryView_Type, "memoryview");
    INIT_TYPE(&PyTuple_Type, "tuple");
    INIT_TYPE(&PyEnum_Type, "enumerate");
    INIT_TYPE(&PyReversed_Type, "reversed");
    INIT_TYPE(&PyStdPrinter_Type, "StdPrinter");
    INIT_TYPE(&PyCode_Type, "code");
    INIT_TYPE(&PyFrame_Type, "frame");
    INIT_TYPE(&PyCFunction_Type, "builtin function");
    INIT_TYPE(&PyMethod_Type, "method");
    INIT_TYPE(&PyFunction_Type, "function");
    INIT_TYPE(&PyDictProxy_Type, "dict proxy");
    INIT_TYPE(&PyGen_Type, "generator");
    INIT_TYPE(&PyGetSetDescr_Type, "get-set descriptor");
    INIT_TYPE(&PyWrapperDescr_Type, "wrapper");
    INIT_TYPE(&_PyMethodWrapper_Type, "method wrapper");
    INIT_TYPE(&PyEllipsis_Type, "ellipsis");
    INIT_TYPE(&PyMemberDescr_Type, "member descriptor");
    INIT_TYPE(&_PyNamespace_Type, "namespace");
    INIT_TYPE(&PyCapsule_Type, "capsule");
    INIT_TYPE(&PyLongRangeIter_Type, "long range iterator");
    INIT_TYPE(&PyCell_Type, "cell");
    INIT_TYPE(&PyInstanceMethod_Type, "instance method");
    INIT_TYPE(&PyClassMethodDescr_Type, "class method descr");
    INIT_TYPE(&PyMethodDescr_Type, "method descr");
    INIT_TYPE(&PyCallIter_Type, "call iter");
    INIT_TYPE(&PySeqIter_Type, "sequence iterator");
    INIT_TYPE(&PyPickleBuffer_Type, "pickle.PickleBuffer");
    INIT_TYPE(&PyCoro_Type, "coroutine");
    INIT_TYPE(&_PyCoroWrapper_Type, "coroutine wrapper");
    INIT_TYPE(&_PyInterpreterID_Type, "interpreter ID");
    return _PyStatus_OK();

#undef INIT_TYPE
}
```

```
int
PyType_Ready(PyTypeObject *type)
{
    PyObject *dict, *bases;
    PyTypeObject *base;
    Py_ssize_t i, n;

    if (type->tp_flags & Py_TPFLAGS_READY) {
        assert(_PyType_CheckConsistency(type));
        return 0;
    }
    _PyObject_ASSERT((PyObject *)type,
                     (type->tp_flags & Py_TPFLAGS_READYING) == 0);

    /* Consistency checks for PEP 590:
     * - Py_TPFLAGS_METHOD_DESCRIPTOR requires tp_descr_get
     * - _Py_TPFLAGS_HAVE_VECTORCALL requires tp_call and
     *   tp_vectorcall_offset > 0
     * To avoid mistakes, we require this before inheriting.
     */
    if (type->tp_flags & Py_TPFLAGS_METHOD_DESCRIPTOR) {
        _PyObject_ASSERT((PyObject *)type, type->tp_descr_get != NULL);
    }
    if (type->tp_flags & _Py_TPFLAGS_HAVE_VECTORCALL) {
        _PyObject_ASSERT((PyObject *)type, type->tp_vectorcall_offset > 0);
        _PyObject_ASSERT((PyObject *)type, type->tp_call != NULL);
    }

    type->tp_flags |= Py_TPFLAGS_READYING;

#ifdef Py_TRACE_REFS
    /* PyType_Ready is the closest thing we have to a choke point
     * for type objects, so is the best place I can think of to try
     * to get type objects into the doubly-linked list of all objects.
     * Still, not all type objects go through PyType_Ready.
     */
    _Py_AddToAllObjects((PyObject *)type, 0);
#endif

    if (type->tp_name == NULL) {
        PyErr_Format(PyExc_SystemError,
                     "Type does not define the tp_name field.");
        goto error;
    }

    /* Initialize tp_base (defaults to BaseObject unless that's us) */
    base = type->tp_base;
    if (base == NULL && type != &PyBaseObject_Type) {
        base = type->tp_base = &PyBaseObject_Type;
        Py_INCREF(base);
    }

    /* Now the only way base can still be NULL is if type is
     * &PyBaseObject_Type.
     */

    /* Initialize the base class */
    if (base != NULL && base->tp_dict == NULL) {
        if (PyType_Ready(base) < 0)
            goto error;
    }

    /* Initialize ob_type if NULL.      This means extensions that want to be
       compilable separately on Windows can call PyType_Ready() instead of
       initializing the ob_type field of their type objects. */
    /* The test for base != NULL is really unnecessary, since base is only
       NULL when type is &PyBaseObject_Type, and we know its ob_type is
       not NULL (it's initialized to &PyType_Type).      But coverity doesn't
       know that. */
    if (Py_TYPE(type) == NULL && base != NULL)
        Py_TYPE(type) = Py_TYPE(base);

    /* Initialize tp_bases */
    bases = type->tp_bases;
    if (bases == NULL) {
        if (base == NULL)
            bases = PyTuple_New(0);
        else
            bases = PyTuple_Pack(1, base);
        if (bases == NULL)
            goto error;
        type->tp_bases = bases;
    }

    /* Initialize tp_dict */
    dict = type->tp_dict;
    if (dict == NULL) {
        dict = PyDict_New();
        if (dict == NULL)
            goto error;
        type->tp_dict = dict;
    }

    /* Add type-specific descriptors to tp_dict */
    if (add_operators(type) < 0)
        goto error;
    if (type->tp_methods != NULL) {
        if (add_methods(type, type->tp_methods) < 0)
            goto error;
    }
    if (type->tp_members != NULL) {
        if (add_members(type, type->tp_members) < 0)
            goto error;
    }
    if (type->tp_getset != NULL) {
        if (add_getset(type, type->tp_getset) < 0)
            goto error;
    }

    /* Calculate method resolution order */
    if (mro_internal(type, NULL) < 0)
        goto error;

    /* Inherit special flags from dominant base */
    if (type->tp_base != NULL)
        inherit_special(type, type->tp_base);

    /* Initialize tp_dict properly */
    bases = type->tp_mro;
    assert(bases != NULL);
    assert(PyTuple_Check(bases));
    n = PyTuple_GET_SIZE(bases);
    for (i = 1; i < n; i++) {
        PyObject *b = PyTuple_GET_ITEM(bases, i);
        if (PyType_Check(b))
            inherit_slots(type, (PyTypeObject *)b);
    }

    /* All bases of statically allocated type should be statically allocated */
    if (!(type->tp_flags & Py_TPFLAGS_HEAPTYPE))
        for (i = 0; i < n; i++) {
            PyObject *b = PyTuple_GET_ITEM(bases, i);
            if (PyType_Check(b) &&
                (((PyTypeObject *)b)->tp_flags & Py_TPFLAGS_HEAPTYPE)) {
                PyErr_Format(PyExc_TypeError,
                             "type '%.100s' is not dynamically allocated but "
                             "its base type '%.100s' is dynamically allocated",
                             type->tp_name, ((PyTypeObject *)b)->tp_name);
                goto error;
            }
        }

    /* Sanity check for tp_free. */
    if (PyType_IS_GC(type) && (type->tp_flags & Py_TPFLAGS_BASETYPE) &&
        (type->tp_free == NULL || type->tp_free == PyObject_Del)) {
        /* This base class needs to call tp_free, but doesn't have
         * one, or its tp_free is for non-gc'ed objects.
         */
        PyErr_Format(PyExc_TypeError, "type '%.100s' participates in "
                     "gc and is a base type but has inappropriate "
                     "tp_free slot",
                     type->tp_name);
        goto error;
    }

    /* if the type dictionary doesn't contain a __doc__, set it from
       the tp_doc slot.
     */
    if (_PyDict_GetItemIdWithError(type->tp_dict, &PyId___doc__) == NULL) {
        if (PyErr_Occurred()) {
            goto error;
        }
        if (type->tp_doc != NULL) {
            const char *old_doc = _PyType_DocWithoutSignature(type->tp_name,
                type->tp_doc);
            PyObject *doc = PyUnicode_FromString(old_doc);
            if (doc == NULL)
                goto error;
            if (_PyDict_SetItemId(type->tp_dict, &PyId___doc__, doc) < 0) {
                Py_DECREF(doc);
                goto error;
            }
            Py_DECREF(doc);
        } else {
            if (_PyDict_SetItemId(type->tp_dict,
                                  &PyId___doc__, Py_None) < 0)
                goto error;
        }
    }

    /* Hack for tp_hash and __hash__.
       If after all that, tp_hash is still NULL, and __hash__ is not in
       tp_dict, set tp_hash to PyObject_HashNotImplemented and
       tp_dict['__hash__'] equal to None.
       This signals that __hash__ is not inherited.
     */
    if (type->tp_hash == NULL) {
        if (_PyDict_GetItemIdWithError(type->tp_dict, &PyId___hash__) == NULL) {
            if (PyErr_Occurred() ||
               _PyDict_SetItemId(type->tp_dict, &PyId___hash__, Py_None) < 0)
            {
                goto error;
            }
            type->tp_hash = PyObject_HashNotImplemented;
        }
    }

    /* Some more special stuff */
    base = type->tp_base;
    if (base != NULL) {
        if (type->tp_as_async == NULL)
            type->tp_as_async = base->tp_as_async;
        if (type->tp_as_number == NULL)
            type->tp_as_number = base->tp_as_number;
        if (type->tp_as_sequence == NULL)
            type->tp_as_sequence = base->tp_as_sequence;
        if (type->tp_as_mapping == NULL)
            type->tp_as_mapping = base->tp_as_mapping;
        if (type->tp_as_buffer == NULL)
            type->tp_as_buffer = base->tp_as_buffer;
    }

    /* Link into each base class's list of subclasses */
    bases = type->tp_bases;
    n = PyTuple_GET_SIZE(bases);
    for (i = 0; i < n; i++) {
        PyObject *b = PyTuple_GET_ITEM(bases, i);
        if (PyType_Check(b) &&
            add_subclass((PyTypeObject *)b, type) < 0)
            goto error;
    }

    /* All done -- set the ready flag */
    type->tp_flags =
        (type->tp_flags & ~Py_TPFLAGS_READYING) | Py_TPFLAGS_READY;
    assert(_PyType_CheckConsistency(type));
    return 0;

  error:
    type->tp_flags &= ~Py_TPFLAGS_READYING;
    return -1;
}
```

有些内置类型还会执行一些特殊的初始化操作。例如，初始化 int 时，需要生成一些小整数，存放在 interp->small_ints 列表中，便于之后复用；初始化 float 时，需要判断浮点数在当前系统中的存储格式。
接下来，pycore_interp_init() 调用 pycore_init_builtins() 执行内置模块的初始化。
内置类型初始化完成后，pycore_interp_init() 调用 _PySys_Create() 创建 sys 模块。
内置模块的内容包括内置函数，如 abs()、dir()、print() 等，内置类型，如 dict、int、str 等，内置异常，如 Exception、ValueError 等，以及内置常数，如 False、Ellipsis、None 等。
其他

#### 主初始化

下一步是主初始化阶段，即 [pyinit_main()]()

1. 获取系统真实时间和单调时间（译者注：系统启动后经历的 ticks），确保 time.time()，time.monotonic()，time.perf_counter() 等函数正常工作。
2. 完成 sys 模块初始化，包括设置路径，如 sys.path，sys.executable，sys.exec_prefix 等，以及调用参数相关变量，如 sys.argv，sys._xoptions 等。
3. 支持基于路径的（外部）模块导入。初始化过程会导入一个冻结模块，importlib._bootstrap_external。它支持基于 sys.path 的模块导入。同时，另一个冻结模块，zipimport，也会被导入，以支持导入 ZIP 压缩格式的模块，也就是说，sys.path 下的文件夹可以是以被压缩格式存在的。
4. 规范文件系统与标准流的编码格式，设置编解码错误处理器。
5. 设置默认的信号处理器，以处理进程接收到的 SIGINT 等系统信号。用户可以通过 signal 模块自定义信号处理器。
6. 导入 io 模块，初始化 sys.stdin、sys.stdout、sys.stderr，本质上就是通过 io.open() 打开标准流对应的文件描述符。
7. 将 builtins.open 设置为 io.OpenWrapper，使用户可以直接使用这个内置函数。
8. 创建 __main__ 模块，将 __main__.__builtins__ 设置为 builtins，__main__.__loader__ 设置为 _frozen_importlib.BuiltinImporter。此时，__main__ 模块中还没有内容。
9. 导入 warnings、site 模块，site 模块会在 sys.path 中添加 /usr/local/lib/python3.9/site-packages/ 相关路径。
10. 将 interp->runtime->initialized 设置为 1。



### 二. 编译
#### 和传统编译器的区别
#### 语言定义(EBNF) -> 解析器 -> 编译器
#### source code -> DFA(LL(1)) -> CST -> AST -> code object
#### 符号表



### 三. 解释

#### 运行栈，帧
#### 线程状态，解释器状态，运行状态

### Python架构

## Python 魔法方法

---

### 对象创建： __new__, __call__, __init__

### 子类：__subclasses__, __init_subclass__

### 描述器协议__get__, __set__, __delete__

### 内存优化：__slots__
