type
  Type* {.size:sizeof(cuint),header: "ApplicationUsage", importcpp: "osg::ApplicationUsage::Type".} = enum
    NO_HELP = 0,
    COMMAND_LINE_OPTION = 1,
    ENVIRONMENTAL_VARIABLE = 2,
    KEYBOARD_MOUSE_BINDING = 4,
    HELP_ALL = 7

  UsageMap* {.header: "ApplicationUsage", importcpp: "osg::ApplicationUsage::UsageMap".} = cint
  ApplicationUsage* {.header: "ApplicationUsage", importcpp: "osg::ApplicationUsage", byref.} = object #of osg::Referenced

  ApplicationUsageProxy* {.header: "ApplicationUsage", importcpp: "osg::ApplicationUsageProxy", byref.} = object



{.push header: "ApplicationUsage".}

proc constructApplicationUsage*(): ApplicationUsage {.constructor,importcpp: "osg::ApplicationUsage::ApplicationUsage".}

proc constructApplicationUsage*(commandLineUsage: String): ApplicationUsage {.constructor,importcpp: "osg::ApplicationUsage::ApplicationUsage(@)".}

proc constructApplicationUsageProxy*(`type`: Type, option: String, explanation: String): ApplicationUsageProxy {.constructor,importcpp: "osg::ApplicationUsageProxy::ApplicationUsageProxy(@)".}
    ## register an explanation of commandline/environmentvariable/keyboard
    ## mouse usage.

proc instance*(this: var ApplicationUsage): ptr Applicationusage   {.importcpp: "instance".}

proc setApplicationName*(this: var ApplicationUsage, name: String)  {.importcpp: "setApplicationName".}
    ## The ApplicationName is often displayed when logging errors, and
    ## frequently incorporated into the Description (below).

proc getApplicationName*(this: ApplicationUsage): String  {.importcpp: "getApplicationName".}

proc setDescription*(this: var ApplicationUsage, desc: String)  {.importcpp: "setDescription".}
    ## If non-empty, the Description is typically shown by the Help Handler
    ## as text on the Help display (which also lists keyboard abbreviations.

proc getDescription*(this: ApplicationUsage): String  {.importcpp: "getDescription".}

proc addUsageExplanation*(this: var ApplicationUsage, `type`: Type, option: String, explanation: String)  {.importcpp: "addUsageExplanation".}

proc setCommandLineUsage*(this: var ApplicationUsage, explanation: String)  {.importcpp: "setCommandLineUsage".}

proc getCommandLineUsage*(this: ApplicationUsage): String  {.importcpp: "getCommandLineUsage".}

proc addCommandLineOption*(this: var ApplicationUsage, option: String, explanation: String, defaultValue: String)  {.importcpp: "addCommandLineOption".}

proc setCommandLineOptions*(this: var ApplicationUsage, usageMap: Usagemap)  {.importcpp: "setCommandLineOptions".}

proc getCommandLineOptions*(this: ApplicationUsage): Usagemap  {.importcpp: "getCommandLineOptions".}

proc setCommandLineOptionsDefaults*(this: var ApplicationUsage, usageMap: Usagemap)  {.importcpp: "setCommandLineOptionsDefaults".}

proc getCommandLineOptionsDefaults*(this: ApplicationUsage): Usagemap  {.importcpp: "getCommandLineOptionsDefaults".}

proc addEnvironmentalVariable*(this: var ApplicationUsage, option: String, explanation: String, defaultValue: String)  {.importcpp: "addEnvironmentalVariable".}

proc setEnvironmentalVariables*(this: var ApplicationUsage, usageMap: Usagemap)  {.importcpp: "setEnvironmentalVariables".}

proc getEnvironmentalVariables*(this: ApplicationUsage): Usagemap  {.importcpp: "getEnvironmentalVariables".}

proc setEnvironmentalVariablesDefaults*(this: var ApplicationUsage, usageMap: Usagemap)  {.importcpp: "setEnvironmentalVariablesDefaults".}

proc getEnvironmentalVariablesDefaults*(this: ApplicationUsage): Usagemap  {.importcpp: "getEnvironmentalVariablesDefaults".}

proc addKeyboardMouseBinding*(this: var ApplicationUsage, prefix: String, key: cint, explanation: String)  {.importcpp: "addKeyboardMouseBinding".}

proc addKeyboardMouseBinding*(this: var ApplicationUsage, key: cint, explanation: String)  {.importcpp: "addKeyboardMouseBinding".}

proc addKeyboardMouseBinding*(this: var ApplicationUsage, option: String, explanation: String)  {.importcpp: "addKeyboardMouseBinding".}

proc setKeyboardMouseBindings*(this: var ApplicationUsage, usageMap: Usagemap)  {.importcpp: "setKeyboardMouseBindings".}

proc getKeyboardMouseBindings*(this: ApplicationUsage): Usagemap  {.importcpp: "getKeyboardMouseBindings".}

proc getFormattedString*(this: var ApplicationUsage, str: String, um: Usagemap, widthOfOutput: cuint = 80, showDefaults: bool, ud: Usagemap = ))  {.importcpp: "getFormattedString".}

proc write*(this: var ApplicationUsage, output: Ostream, um: Usagemap, widthOfOutput: cuint = 80, showDefaults: bool, ud: Usagemap = ))  {.importcpp: "write".}

proc write*(this: var ApplicationUsage, output: Ostream, `type`: cuint, widthOfOutput: cuint = 80, showDefaults: bool)  {.importcpp: "write".}

proc writeEnvironmentSettings*(this: var ApplicationUsage, output: Ostream)  {.importcpp: "writeEnvironmentSettings".}

{.pop.}  # header: "ApplicationUsage"
