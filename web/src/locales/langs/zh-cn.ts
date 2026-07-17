const local: App.I18n.BaseSchema = {
  system: {
    title: 'AgenticBI 管理系统',
    updateTitle: '系统版本更新通知',
    updateContent: '检测到系统有新版本发布，是否立即刷新页面？',
    updateConfirm: '立即刷新',
    updateCancel: '稍后再说'
  },
  common: {
    action: '操作',
    add: '新增',
    addSuccess: '添加成功',
    backToHome: '返回首页',
    copy: '复制',
    batchDelete: '批量删除',
    batchApprove: '批量通过',
    batchReject: '批量拒绝',
    cancel: '取消',
    close: '关闭',
    check: '勾选',
    selectAll: '全选',
    expandColumn: '展开列',
    columnSetting: '列设置',
    config: '配置',
    confirm: '确认',
    delete: '删除',
    deleteSuccess: '删除成功',
    confirmDelete: '确认删除吗？',
    approve: '通过',
    approveSuccess: '通过成功',
    confirmApprove: '确认通过吗？',
    reject: '拒绝',
    rejectSuccess: '拒绝成功',
    confirmReject: '确认拒绝吗？',
    edit: '编辑',
    view: '查看',
    warning: '警告',
    error: '错误',
    index: '序号',
    keywordSearch: '请输入关键词搜索',
    logout: '退出登录',
    logoutConfirm: '确认退出登录吗？',
    lookForward: '敬请期待',
    modify: '修改',
    modifySuccess: '修改成功',
    noData: '无数据',
    operate: '操作',
    pleaseCheckValue: '请检查输入的值是否合法',
    refresh: '刷新',
    reset: '重置',
    search: '搜索',
    switch: '切换',
    tip: '提示',
    trigger: '触发',
    update: '更新',
    updateSuccess: '更新成功',
    userCenter: '个人中心',
    yesOrNo: {
      yes: '是',
      no: '否'
    }
  },
  request: {
    logout: '请求失败后登出用户',
    logoutMsg: '用户状态失效，请重新登录',
    logoutWithModal: '请求失败后弹出模态框再登出用户',
    logoutWithModalMsg: '用户状态失效，请重新登录',
    refreshToken: '请求的token已过期，刷新token',
    tokenExpired: 'token已过期'
  },
  theme: {
    themeDrawerTitle: '主题配置',
    tabs: {
      appearance: '外观',
      layout: '布局',
      general: '通用',
      preset: '预设'
    },
    appearance: {
      themeSchema: {
        title: '主题模式',
        light: '亮色模式',
        dark: '暗黑模式',
        auto: '跟随系统'
      },
      grayscale: '灰色模式',
      colourWeakness: '色弱模式',
      themeColor: {
        title: '主题颜色',
        primary: '主色',
        info: '信息色',
        success: '成功色',
        warning: '警告色',
        error: '错误色',
        followPrimary: '跟随主色'
      },
      themeRadius: {
        title: '主题圆角'
      },
      recommendColor: '应用推荐算法的颜色',
      recommendColorDesc: '推荐颜色的算法参照',
      preset: {
        title: '主题预设',
        apply: '应用',
        applySuccess: '预设应用成功',
        default: {
          name: '默认预设',
          desc: 'AgenticBIAdmin 默认主题预设'
        },
        dark: {
          name: '暗色预设',
          desc: '适用于夜间使用的暗色主题预设'
        },
        compact: {
          name: '紧凑型',
          desc: '适用于小屏幕的紧凑布局预设'
        },
        azir: {
          name: 'Azir的预设',
          desc: '是 Azir 比较喜欢的莫兰迪色系冷淡风'
        }
      }
    },
    layout: {
      layoutMode: {
        title: '布局模式',
        vertical: '左侧菜单模式',
        'vertical-mix': '左侧菜单混合模式',
        'vertical-hybrid-header-first': '左侧混合-顶部优先',
        horizontal: '顶部菜单模式',
        'top-hybrid-sidebar-first': '顶部混合-侧边优先',
        'top-hybrid-header-first': '顶部混合-顶部优先',
        vertical_detail: '左侧菜单布局，菜单在左，内容在右。',
        'vertical-mix_detail': '左侧双菜单布局，一级菜单在左侧深色区域，二级菜单在左侧浅色区域。',
        'vertical-hybrid-header-first_detail':
          '左侧混合布局，一级菜单在顶部，二级菜单在左侧深色区域，三级菜单在左侧浅色区域。',
        horizontal_detail: '顶部菜单布局，菜单在顶部，内容在下方。',
        'top-hybrid-sidebar-first_detail': '顶部混合布局，一级菜单在左侧，二级菜单在顶部。',
        'top-hybrid-header-first_detail': '顶部混合布局，一级菜单在顶部，二级菜单在左侧。'
      },
      tab: {
        title: '标签栏设置',
        visible: '显示标签栏',
        cache: '标签栏信息缓存',
        cacheTip: '一键开启/关闭全局 keepalive',
        height: '标签栏高度',
        mode: {
          title: '标签栏风格',
          slider: '滑块风格',
          chrome: '谷歌风格',
          button: '按钮风格'
        },
        closeByMiddleClick: '鼠标中键关闭标签页',
        closeByMiddleClickTip: '启用后可以使用鼠标中键点击标签页进行关闭'
      },
      header: {
        title: '头部设置',
        height: '头部高度',
        breadcrumb: {
          visible: '显示面包屑',
          showIcon: '显示面包屑图标'
        }
      },
      sider: {
        title: '侧边栏设置',
        inverted: '深色侧边栏',
        width: '侧边栏宽度',
        collapsedWidth: '侧边栏折叠宽度',
        mixWidth: '混合布局侧边栏宽度',
        mixCollapsedWidth: '混合布局侧边栏折叠宽度',
        mixChildMenuWidth: '混合布局子菜单宽度',
        autoSelectFirstMenu: '自动选择第一个子菜单',
        autoSelectFirstMenuTip: '点击一级菜单时，自动选择并导航到第一个子菜单的最深层级'
      },
      footer: {
        title: '底部设置',
        visible: '显示底部',
        fixed: '固定底部',
        height: '底部高度',
        right: '底部居右'
      },
      content: {
        title: '内容区域设置',
        scrollMode: {
          title: '滚动模式',
          tip: '主题滚动仅 main 部分滚动，外层滚动可携带头部底部一起滚动',
          wrapper: '外层滚动',
          content: '主体滚动'
        },
        page: {
          animate: '页面切换动画',
          mode: {
            title: '页面切换动画类型',
            'fade-slide': '滑动',
            fade: '淡入淡出',
            'fade-bottom': '底部消退',
            'fade-scale': '缩放消退',
            'zoom-fade': '渐变',
            'zoom-out': '闪现',
            none: '无'
          }
        },
        fixedHeaderAndTab: '固定头部和标签栏'
      }
    },
    general: {
      title: '通用设置',
      watermark: {
        title: '水印设置',
        visible: '显示全屏水印',
        text: '自定义水印文本',
        enableUserName: '启用用户名水印',
        enableTime: '显示当前时间',
        timeFormat: '时间格式'
      },
      multilingual: {
        title: '多语言设置',
        visible: '显示多语言按钮'
      },
      globalSearch: {
        title: '全局搜索设置',
        visible: '显示全局搜索按钮'
      }
    },
    configOperation: {
      copyConfig: '复制配置',
      copySuccessMsg: '复制成功，请替换 src/theme/settings.ts 中的变量 themeSettings',
      resetConfig: '重置配置',
      resetSuccessMsg: '重置成功'
    }
  },
  route: {
    login: '登录',
    403: '无权限',
    404: '页面不存在',
    500: '服务器错误',
    'iframe-page': '外链页面',
    home: '首页',
    document: '文档',
    document_project: '项目文档',
    'document_project-link': '项目文档(外链)',
    document_video: '视频教程',
    document_vue: 'Vue文档',
    document_vite: 'Vite文档',
    document_unocss: 'UnoCSS文档',
    document_naive: 'Naive UI文档',
    'document_pro-naive': 'Pro Naive UI文档',
    document_antd: 'Ant Design Vue文档',
    document_alova: 'Alova文档',
    'user-center': '个人中心',
    about: '关于',
    function: '系统功能',
    alova: 'alova示例',
    alova_request: 'alova请求',
    alova_scenes: '场景化请求',
    'pro-naive': 'Pro Naive UI 示例',
    'pro-naive_form': '表单',
    'pro-naive_form_basic': '基础表单',
    'pro-naive_form_query': '查询表单',
    'pro-naive_form_step': '分步表单',
    'pro-naive_table': '表格',
    'pro-naive_table_remote': '远程加载',
    'pro-naive_table_row-edit': '行编辑',
    function_tab: '标签页',
    'function_multi-tab': '多标签页',
    'function_hide-child': '隐藏子菜单',
    'function_hide-child_one': '隐藏子菜单',
    'function_hide-child_two': '菜单二',
    'function_hide-child_three': '菜单三',
    function_request: '请求',
    'function_toggle-auth': '切换权限',
    'function_super-page': '超级管理员可见',
    manage: '系统管理',
    manage_api: 'API管理',
    manage_user: '用户管理',
    'manage_user-detail': '用户详情',
    manage_role: '角色管理',
    manage_menu: '菜单管理',
    manage_codegen: '代码生成',
    manage_radar: '性能监控',
    manage_radar_overview: '仪表盘',
    manage_radar_requests: '请求列表',
    manage_radar_queries: 'SQL查询',
    manage_radar_exceptions: '异常列表',
    manage_radar_monitor: '系统监控',
    hr: 'HR管理',
    'hr_my-workspace': '我的工作台',
    hr_team: '我的团队',
    hr_employee: '员工管理',
    hr_department: '部门管理',
    hr_tag: '标签管理',
    showcase: '数据展示（公开）',
    'multi-menu': '多级菜单',
    'multi-menu_first': '菜单一',
    'multi-menu_first_child': '菜单一子菜单',
    'multi-menu_second': '菜单二',
    'multi-menu_second_child': '菜单二子菜单',
    'multi-menu_second_child_home': '菜单二子菜单首页',
    exception: '异常页',
    exception_403: '403',
    exception_404: '404',
    exception_500: '500',
    bi: '智能 BI',
    bi_chat: '对话工作台',
    bi_metadata: '元数据中心',
    bi_models: '模型管理',
    'bi_sql-workbench': 'SQL 工作台',
    bi_audit: '审计面板',
    plugin: '插件示例',
    plugin_copy: '剪贴板',
    plugin_charts: '图表',
    plugin_charts_echarts: 'ECharts',
    plugin_charts_antv: 'AntV',
    plugin_charts_vchart: 'VChart',
    plugin_editor: '编辑器',
    plugin_editor_quill: '富文本编辑器',
    plugin_editor_markdown: 'MD 编辑器',
    plugin_icon: '图标',
    plugin_map: '地图',
    plugin_print: '打印',
    plugin_swiper: 'Swiper',
    plugin_video: '视频',
    plugin_barcode: '条形码',
    plugin_pinyin: '拼音',
    plugin_excel: 'Excel',
    plugin_pdf: 'PDF 预览',
    plugin_gantt: '甘特图',
    plugin_gantt_dhtmlx: 'dhtmlxGantt',
    plugin_gantt_vtable: 'VTableGantt',
    plugin_typeit: '打字机',
    plugin_tables: '表格',
    plugin_tables_vtable: 'VTable'
  },
  page: {
    login: {
      common: {
        loginOrRegister: '登录 / 注册',
        userNamePlaceholder: '请输入用户名',
        phonePlaceholder: '请输入手机号',
        codePlaceholder: '请输入验证码',
        passwordPlaceholder: '请输入密码',
        confirmPasswordPlaceholder: '请再次输入密码',
        codeLogin: '验证码登录',
        confirm: '确定',
        back: '返回',
        validateSuccess: '验证成功',
        loginSuccess: '登录成功',
        welcomeBack: '欢迎回来，{nickName} ！'
      },
      pwdLogin: {
        title: '密码登录',
        rememberMe: '记住我',
        forgetPassword: '忘记密码？',
        register: '注册账号',
        otherAccountLogin: '其他账号登录',
        otherLoginMode: '其他登录方式',
        superAdmin: '超级管理员',
        admin: '管理员',
        user: '普通用户'
      },
      codeLogin: {
        title: '验证码登录',
        getCode: '获取验证码',
        reGetCode: '{time}秒后重新获取',
        sendCodeSuccess: '验证码发送成功',
        imageCodePlaceholder: '请输入图片验证码'
      },
      register: {
        title: '注册账号',
        agreement: '我已经仔细阅读并接受',
        protocol: '《用户协议》',
        policy: '《隐私权政策》'
      },
      resetPwd: {
        title: '重置密码'
      },
      bindWeChat: {
        title: '绑定微信'
      }
    },
    about: {
      title: '关于',
      introduction: `AgenticBIAdmin 是一个面向 AI Agent 时代的智能分析后台，基于最新的前后端技术栈，包括 FastAPI、Vue3、Vite、TypeScript、Pinia 和 UnoCSS。它内置了事件总线、行级权限、智能体编排等能力，代码规范严谨，实现了自动化的文件路由系统。AgenticBIAdmin 致力于让业务模块可由 AI 自动生成与维护，为您提供一站式的智能分析解决方案，无需额外配置，开箱即用。同样是一个快速学习 Agentic AI 与现代后台架构的最佳实践。`,
      projectInfo: {
        title: '项目信息',
        version: '版本',
        latestBuildTime: '最新构建时间',
        githubLink: 'Github 地址',
        previewLink: '预览地址'
      },
      prdDep: '生产依赖',
      devDep: '开发依赖'
    },
    home: {
      branchDesc:
        '为了方便大家开发和更新合并，我们对main分支的代码进行了精简，只保留了首页菜单，其余内容已移至example分支进行维护。预览地址显示的内容即为example分支的内容。',
      greeting: '早安，{userName}, 今天又是充满活力的一天!',
      weatherDesc: '今日多云转晴，20℃ - 25℃!',
      projectCount: '项目数',
      todo: '待办',
      message: '消息',
      downloadCount: '下载量',
      registerCount: '注册量',
      schedule: '作息安排',
      study: '学习',
      work: '工作',
      rest: '休息',
      entertainment: '娱乐',
      visitCount: '访问量',
      turnover: '成交额',
      dealCount: '成交量',
      projectNews: {
        title: '项目动态',
        moreNews: '更多动态',
        desc1: 'AgenticBIAdmin 项目启动，定位为 AI Agent 驱动的智能分析后台。',
        desc2: '团队落地了事件总线 + 周期任务 + 行级权限的异步架构骨架。',
        desc3: 'AgenticBIAdmin 接入首个智能体编排能力，业务模块可由 AI 自动生成。',
        desc4: '我们正在编写"自然语言到数据洞察"的下一代文档！',
        desc5: 'AgenticBIAdmin 智能工作台初版成型，先凑合看！'
      },
      creativity: '创意'
    },
    function: {
      tab: {
        tabOperate: {
          title: '标签页操作',
          addTab: '添加标签页',
          addTabDesc: '跳转到关于页面',
          closeTab: '关闭标签页',
          closeCurrentTab: '关闭当前标签页',
          closeAboutTab: '关闭"关于"标签页',
          addMultiTab: '添加多标签页',
          addMultiTabDesc1: '跳转到多标签页页面',
          addMultiTabDesc2: '跳转到多标签页页面(带有查询参数)'
        },
        tabTitle: {
          title: '标签页标题',
          changeTitle: '修改标题',
          change: '修改',
          resetTitle: '重置标题',
          reset: '重置'
        }
      },
      multiTab: {
        routeParam: '路由参数',
        backTab: '返回 function_tab'
      },
      toggleAuth: {
        toggleAccount: '切换账号',
        authHook: '权限钩子函数 `hasAuth`',
        superAdminVisible: '超级管理员可见',
        adminVisible: '管理员可见',
        adminOrUserVisible: '管理员和用户可见'
      },
      request: {
        repeatedErrorOccurOnce: '重复请求错误只出现一次',
        repeatedError: '重复请求错误',
        repeatedErrorMsg1: '自定义请求错误 1',
        repeatedErrorMsg2: '自定义请求错误 2'
      }
    },
    alova: {
      scenes: {
        captchaSend: '发送验证码',
        autoRequest: '自动请求',
        visibilityRequestTips: '浏览器窗口切换自动请求数据',
        pollingRequestTips: '每3秒自动请求一次',
        networkRequestTips: '网络重连后自动请求',
        refreshTime: '更新时间',
        startRequest: '开始请求',
        stopRequest: '停止请求',
        requestCrossComponent: '跨组件触发请求',
        triggerAllRequest: '手动触发所有自动请求'
      }
    },
    proNaive: {
      form: {
        basic: {
          title: '基础示例',
          appName: '应用名称',
          appStatus: '应用状态',
          createTime: '创建时间',
          responseDate: '响应日期',
          specificationInfo: '规格信息',
          specificate: '规格',
          specificationName: '规格名',
          specificationValue: '规格值',
          specificationColorRed: '红',
          specificationColorOrange: '橙',
          addSpecificateItem: '添加规格项',
          fillValue: '填充值',
          reset: '重置',
          submit: '提交',
          add: '新建',
          delete: '删除',
          color: '颜色',
          normal: '正常',
          anomaly: '异常'
        },
        query: {
          title1: '查询表单，默认展开',
          title2: '查询表单，默认折叠，折叠时保留2行',
          appName: '应用名称',
          appStatus: '应用状态',
          createTime: '创建时间',
          responseDate: '响应日期',
          endDate: '结束日期',
          field: '字段'
        },
        step: {
          title: '分步表单',
          step1: {
            title: '表单1',
            field: '表单1字段',
            nextStep: '下一步'
          },
          step2: {
            title: '表单2',
            field: '表单2字段',
            prevStep: '上一步',
            submit: '提交'
          }
        }
      },
      table: {
        remote: {
          filterCondition: '筛选条件',
          name: '名称',
          createTime: '创建时间',
          responseTime: '响应时间',
          title: '远程加载',
          replicableText: '可复制文本',
          tags: 'tags',
          dateFormatting: '日期格式化',
          image: '图片'
        },
        rowEdit: {
          title: '编辑表格',
          reset: '重置',
          submit: '提交',
          edit: '编辑',
          delete: '删除',
          save: '保存',
          task: '任务',
          score: '评分',
          time: '时间',
          name: '名称',
          action: '操作'
        }
      }
    },
    manage: {
      common: {
        statusType: {
          enable: '启用',
          disable: '禁用'
        },
        updatedInfo: '更新信息',
        updatedBy: '更新人',
        updatedAt: '更新时间',
        createdBy: '创建人',
        createdAt: '创建时间'
      },
      role: {
        title: '角色列表',
        roleName: '角色名称',
        roleCode: '角色编码',
        rolestatusType: '角色状态',
        roleDesc: '角色描述',
        menuAuth: '菜单权限',
        buttonAuth: '按钮权限',
        apiAuth: 'API权限',
        form: {
          roleName: '请输入角色名称',
          roleCode: '请输入角色编码',
          rolestatusType: '请选择角色状态',
          roleDesc: '请输入角色描述'
        },
        addRole: '新增角色',
        editRole: '编辑角色'
      },
      api: {
        title: 'API列表',
        path: 'API路径',
        method: '请求方式',
        summary: 'API简介',
        tags: '标签',
        statusType: 'API状态',
        includeSystem: '包含系统接口',
        form: {
          path: '请输入API路径',
          method: '请选择请求方式',
          summary: '请输入API简介',
          tags: '请选择标签',
          statusType: '请选择API状态'
        },
        addApi: '新增API',
        editApi: '编辑API',
        methods: {
          GET: 'GET',
          POST: 'POST',
          PUT: 'PUT',
          PATCH: 'PATCH',
          DELETE: 'DELETE'
        }
      },
      user: {
        title: '用户列表',
        userName: '用户名',
        password: '密码',
        userGender: '性别',
        nickName: '昵称',
        userPhone: '手机号',
        userEmail: '邮箱',
        userStatusType: '用户状态',
        userRole: '用户角色',
        form: {
          userName: '请输入用户名',
          password: '请输入密码',
          passwordEditHint: '不填则不修改密码',
          userGender: '请选择性别',
          nickName: '请输入昵称',
          userPhone: '请输入手机号',
          userEmail: '请输入邮箱',
          userStatusType: '请选择用户状态',
          userRole: '请选择用户角色'
        },
        offline: '下线',
        batchOffline: '批量下线',
        confirmOffline: '确认将该用户强制下线吗？',
        offlineSuccess: '下线成功',
        impersonate: {
          button: '模拟登录',
          confirm: '确认以 {name} 的身份模拟登录吗？',
          switchSuccess: '模拟登录成功',
          nowActingAs: '当前正在模拟用户 {name}',
          actingAs: '模拟中: {name}',
          exit: '退出模拟',
          exitSuccess: '已退出模拟登录'
        },
        addUser: '新增用户',
        editUser: '编辑用户',
        gender: {
          male: '男',
          female: '女',
          unknow: '未知'
        }
      },
      menu: {
        home: '首页',
        title: '菜单列表',
        id: 'ID',
        parentId: '父级菜单',
        menuType: '菜单类型',
        menuName: '菜单名称',
        routeName: '路由名称',
        routePath: '路由路径',
        pathParam: '路径参数',
        layout: '布局',
        page: '页面组件',
        i18nKey: '国际化key',
        icon: '图标',
        localIcon: '本地图标',
        iconTypeTitle: '图标类型',
        order: '排序',
        constant: '常量路由',
        keepAlive: '缓存路由',
        href: '外链',
        hideInMenu: '隐藏菜单',
        activeMenu: '高亮的菜单',
        multiTab: '支持多页签',
        fixedIndexInTab: '固定在页签中的序号',
        query: '路由参数',
        button: '按钮',
        buttonCode: '按钮编码',
        buttonDesc: '按钮描述',
        menuStatusType: '菜单状态',
        form: {
          home: '请选择首页',
          menuType: '请选择菜单类型',
          menuName: '请输入菜单名称',
          routeName: '请输入路由名称',
          routePath: '请输入路由路径',
          pathParam: '请输入路径参数',
          page: '请选择页面组件',
          layout: '请选择布局组件',
          i18nKey: '请输入国际化key',
          icon: '请输入图标',
          localIcon: '请选择本地图标',
          order: '请输入排序',
          keepAlive: '请选择是否缓存路由',
          href: '请输入外链',
          hideInMenu: '请选择是否隐藏菜单',
          activeMenu: '请选择高亮的菜单的路由名称',
          multiTab: '请选择是否支持多标签',
          fixedInTab: '请选择是否固定在页签中',
          fixedIndexInTab: '请输入固定在页签中的序号',
          queryKey: '请输入路由参数Key',
          queryValue: '请输入路由参数Value',
          button: '请选择是否按钮',
          buttonCode: '请输入按钮编码',
          buttonDesc: '请输入按钮描述',
          menuStatusType: '请选择菜单状态'
        },
        addMenu: '新增菜单',
        editMenu: '编辑菜单',
        addChildMenu: '新增子菜单',
        includeBusiness: '业务菜单',
        includeBusinessWarningTitle: '确认显示业务菜单？',
        includeBusinessWarning:
          '业务菜单由各业务模块的 init_data.py 声明，启用 reconcile_menu_subtree 的子树在服务重启时会根据声明重建——手动删除的菜单会被恢复，手动新增的菜单会被清除。',
        dontShowAgain: '不再提示',
        type: {
          directory: '目录',
          menu: '菜单'
        },
        iconType: {
          iconify: 'iconify图标',
          local: '本地图标'
        }
      },
      radar: {
        purge: '清理数据',
        purgeConfirm: '确定清理24小时前的监控数据？',
        purgeSuccess: '已清理记录数',
        overview: {
          title: '仪表盘',
          requestCount: '总请求数',
          avgDuration: '平均耗时',
          errorCount: '异常数',
          errorRate: '异常率',
          queryCount: 'SQL查询数',
          slowQueryCount: '慢查询数',
          userLogCount: '用户日志数'
        },
        dashboard: {
          totalRequests: '总请求数',
          avgResponseTime: '平均响应时间',
          dbQueries: '数据库查询',
          exceptions: '异常数',
          perfOverview: '性能概览',
          successRate: '成功率',
          errorRate: '错误率',
          rps: '每秒请求数',
          responseTime: '响应时间',
          queryPerf: '查询性能',
          requestDist: '请求分布',
          responseTimeTrend: '响应时间趋势',
          queryActivity: '数据库活动'
        },
        monitor: {
          title: '系统监控',
          autoRefresh: '自动刷新',
          paused: '已暂停',
          cpuUsage: 'CPU使用率',
          cores: '核心',
          threads: '线程',
          memoryUsage: '内存使用率',
          used: '已使用',
          total: '总计',
          diskUsage: '磁盘使用率',
          diskIO: '磁盘IO',
          read: '读取',
          write: '写入',
          totalRead: '总读取',
          totalWrite: '总写入',
          networkIO: '网络IO',
          activeConnections: '活跃连接',

          upload: '上传',
          download: '下载',
          totalSent: '总发送',
          totalRecv: '总接收',
          basicInfo: '基本信息',
          hostname: '主机名',
          ipAddress: 'IP地址',
          os: '操作系统',
          architecture: '架构',
          processor: '处理器',
          pythonVersion: 'Python版本',
          systemStatus: '系统状态',
          systemLoad: '系统负载',
          loadAvg: '1/5/15 分钟平均负载',
          uptime: '运行时间',
          bootTime: '启动时间',
          processes: '进程数',
          running: '运行中',
          sleeping: '休眠中',
          onlineUsers: '在线用户',
          updateTime: '更新时间',
          networkTrend: '网络使用趋势',
          topProcesses: 'Top 10 进程',
          processName: '进程名',
          memPercent: '内存%',
          status: '状态',
          createTime: '创建时间'
        },
        requests: {
          title: '请求列表',
          method: '请求方法',
          path: '请求路径',
          status: '状态码',
          businessCode: '业务码',
          businessMsg: '业务消息',
          duration: '耗时',
          error: '异常',
          createdAt: '时间',
          detail: '请求详情',
          queryParams: '查询参数',
          minDuration: '最小耗时',
          hasError: '是否异常',
          xRequestId: '请求ID',
          clientIp: '客户端IP',
          requestHeaders: '请求头',
          requestBody: '请求体',
          responseHeaders: '响应头',
          responseBody: '响应体'
        },
        queries: {
          title: 'SQL查询列表',
          operation: '操作类型',
          connection: '连接',
          slowOnly: '仅慢查询',
          threshold: '阈值'
        },
        exceptions: {
          title: '异常列表',
          errorType: '异常类型',
          errorMessage: '异常消息',
          detail: '异常详情',
          status: '处理状态',
          resolved: '已处理',
          unresolved: '未处理'
        },
        userLogs: {
          title: '用户日志'
        }
      }
    },
    userCenter: {
      profile: {
        title: '个人信息',
        userName: '用户名',
        nickName: '昵称',
        roles: '角色',
        impersonating: '当前为模拟登录'
      },
      password: {
        title: '修改密码',
        oldPassword: '原密码',
        newPassword: '新密码',
        confirmPassword: '确认新密码',
        oldPasswordPlaceholder: '请输入原密码',
        newPasswordPlaceholder: '请输入新密码',
        confirmPasswordPlaceholder: '请再次输入新密码',
        submit: '提交',
        success: '密码修改成功，请重新登录'
      }
    },
    bi: {
      metadata: {
        title: '元数据中心',
        datasource: {
          title: '数据源',
          add: '新增数据源',
          edit: '编辑数据源',
          name: '数据源名称',
          type: '类型',
          host: '主机',
          port: '端口',
          database: '数据库 / 文件',
          username: '用户名',
          password: '密码',
          passwordPlaceholder: '不修改请留空',
          isDefault: '租户默认',
          statusType: '状态',
          remark: '备注',
          lastSyncedAt: '最近同步',
          notSynced: '未同步',
          demoConfirm:
            '将为「默认租户」生成电商演示 SQLite 库（10 类 / 50 商品 / 8 客户 / 5 千订单），并自动同步元数据。是否继续？',
          demoBootstrap: '生成 Demo',
          test: '测试连接',
          sync: '同步元数据',
          testOk: '连接成功',
          testFailed: '连接失败',
          syncSuccess: '同步完成：新增 {tables} 张表、{columns} 列',
          syncFailed: '同步失败',
          empty: '暂无数据源，点击「生成 Demo」可一键创建演示库',
          form: {
            name: '请输入数据源名称',
            type: '请选择类型',
            database: '请输入数据库名 / SQLite 文件名',
            host: '请输入主机（SQLite 可留空）',
            port: '请输入端口',
            username: '请输入用户名',
            password: '请输入密码',
            isDefault: '请选择是否为租户默认',
            remark: '请输入备注'
          },
          typeLabel: {
            postgresql: 'PostgreSQL',
            mysql: 'MySQL',
            clickhouse: 'ClickHouse',
            trino: 'Trino',
            sqlite: 'SQLite'
          }
        },
        table: {
          title: '表清单',
          filterDatasource: '按数据源筛选',
          all: '全部',
          name: '表名',
          schemaName: 'Schema',
          description: '业务描述',
          tags: '标签',
          version: '版本',
          lastSyncedAt: '同步时间',
          columnCount: '列数',
          empty: '该数据源尚未同步元数据，点击数据源「同步元数据」可拉取表结构',
          refresh: '刷新表清单',
          viewColumns: '查看列',
          detailTitle: '表详情：{name}'
        },
        column: {
          title: '列清单',
          name: '列名',
          dataType: '类型',
          nullable: '可空',
          description: '业务描述',
          isDimension: '维度',
          isMetric: '度量',
          sampleValues: '采样值',
          ordinal: '位置'
        }
      },
      sqlworkbench: {
        title: 'SQL 工作台',
        subtitle: '专业用户直接执行 SQL，默认只读；EXPLAIN 给出执行计划。',
        datasource: '数据源',
        chooseDatasource: '请先选择数据源',
        placeholder:
          '-- 输入 SQL（仅 SELECT / WITH；多条用 ; 分隔，尾分号可省略）\nSELECT name, price\nFROM products\nORDER BY price DESC\nLIMIT 10;',
        actions: {
          run: '执行',
          explain: 'EXPLAIN',
          format: '格式化',
          clear: '清空',
          copy: '复制 SQL',
          copyFinal: '复制执行后 SQL'
        },
        allowWrite: '允许写操作（INSERT/UPDATE/DELETE，需要授权）',
        result: {
          empty: '尚无执行结果',
          loading: '正在执行…',
          rowCount: '返回 {count} 行，耗时 {ms} ms',
          masked: '脱敏列：{cols}',
          finalSql: '执行后 SQL',
          page: '每页 {size} 条 · 第 {page} 页'
        },
        explain: {
          title: 'EXPLAIN 执行计划',
          empty: '点击「EXPLAIN」查看当前 SQL 的执行计划',
          cost: '耗时 {ms} ms',
          rawSql: '包装后语句'
        },
        history: {
          title: '执行历史',
          empty: '尚无历史',
          refresh: '刷新',
          status: '状态',
          statusLabel: {
            success: '成功',
            failed: '失败',
            timeout: '超时',
            denied: '拒绝'
          },
          rowCount: '行数',
          cost: '耗时',
          time: '时间',
          sql: 'SQL',
          error: '错误',
          deniedHint: '沙箱拒绝执行'
        },
        messages: {
          noDs: '请先选择数据源',
          emptySql: '请输入 SQL',
          noPermission: '当前角色没有该操作权限',
          runOk: '执行成功',
          runDenied: '沙箱拒绝执行：{msg}',
          runFailed: '执行失败：{msg}'
        }
      },
      chat: {
        title: '对话工作台',
        subtitle: '用自然语言问数据，Agent 自动生成 SQL 并执行。',
        newSession: '新建会话',
        sessionList: '会话列表',
        emptySession: '暂无会话，点击"新建会话"开始',
        datasource: '数据源',
        chooseDatasource: '请选择数据源',
        placeholder: '问个问题吧～例如：查询价格最高的 5 个产品',
        send: '发送',
        stop: '停止',
        thinking: '思考中…',
        steps: {
          intent: '意图识别',
          sql_gen: '生成 SQL',
          validate: 'SQL 校验',
          executor: '沙箱执行',
          explain: '结果解读'
        },
        result: {
          title: '查询结果',
          rowCount: '{count} 行',
          costMs: '耗时 {ms} ms',
          tokens: 'Tokens {n}',
          masked: '脱敏列：{cols}'
        },
        finalSql: '执行后 SQL',
        noData: '本次查询无返回数据',
        error: '执行出错',
        sessionTitle: '会话 #{id}'
      },
      models: {
        title: '模型管理',
        subtitle: '配置多家 LLM 提供商与模型；DB 优先，环境变量兜底。',
        provider: {
          title: '提供商',
          add: '新增提供商',
          edit: '编辑提供商',
          name: '名称',
          code: '编码',
          type: '协议',
          displayName: '展示名',
          baseUrl: 'Base URL',
          apiKey: 'API Key',
          apiKeyMasked: 'API Key（脱敏）',
          apiKeyPlaceholder: '不修改请留空',
          isEnabled: '启用',
          isDefault: '默认',
          order: '排序',
          statusType: '状态',
          remark: '备注',
          lastTestedAt: '最近测试',
          lastTestOk: '测试结果',
          lastTestOkLabel: {
            true: '成功',
            false: '失败',
            null: '未测试'
          },
          modelCount: '模型数',
          test: '测试连通',
          testOk: '连通成功',
          testFailed: '连通失败：{msg}',
          empty: '暂无提供商，点击「新增提供商」可接入第一个 LLM',
          form: {
            name: '请输入提供商名称',
            code: '请输入编码（英文，如 deepseek）',
            type: '请选择协议',
            displayName: '请输入展示名',
            baseUrl: '请输入 Base URL（可空，将按 type 预填）',
            apiKey: '请输入 API Key',
            order: '请输入排序',
            remark: '请输入备注'
          },
          typeLabel: {
            openai_compatible: 'OpenAI 兼容',
            anthropic: 'Anthropic',
            ollama: 'Ollama',
            mock: 'Mock',
            custom: '自定义'
          }
        },
        model: {
          title: '模型',
          add: '新增模型',
          edit: '编辑模型',
          provider: '所属提供商',
          code: '模型编码',
          displayName: '展示名',
          type: '用途',
          contextWindow: '上下文窗口',
          inputPrice: '输入价格',
          outputPrice: '输出价格',
          defaultParams: '默认参数（JSON）',
          capabilities: '能力位',
          isEnabled: '启用',
          isDefault: '默认',
          order: '排序',
          statusType: '状态',
          remark: '备注',
          empty: '暂无模型，点击「新增模型」可添加',
          form: {
            provider: '请选择提供商',
            code: '请输入模型编码',
            displayName: '请输入展示名',
            type: '请选择用途',
            contextWindow: '请输入上下文窗口大小',
            inputPrice: '请输入输入价格',
            outputPrice: '请输入输出价格',
            order: '请输入排序',
            remark: '请输入备注'
          },
          typeLabel: {
            chat: '对话',
            embedding: 'Embedding',
            vision: '视觉'
          },
          capabilityLabel: {
            function_call: '工具调用',
            reasoning: '推理',
            json_mode: 'JSON 模式',
            vision: '视觉',
            streaming: '流式'
          }
        }
      },
      audit: {
        title: '审计面板',
        subtitle: '查询/导出/CRUD 全量审计：操作追溯、SQL 回放、趋势分析、时段热力图。',
        kpi: {
          total: '总操作数',
          success: '成功',
          failed: '失败',
          activeUsers: '活跃用户',
          avgCost: '平均耗时'
        },
        filter: {
          timeRange: '时间范围',
          userId: '用户ID',
          keyword: 'SQL哈希 / IP',
          action: '操作类型',
          status: '状态',
          query: '查询',
          reset: '重置',
          export: '导出 CSV'
        },
        tab: {
          list: '审计列表',
          trend: '按天趋势',
          heatmap: '时段热力图'
        },
        table: {
          time: '时间',
          user: '用户',
          action: 'Action',
          status: '状态',
          datasource: '数据源',
          sqlHash: 'SQL 摘要',
          rowCount: '行数',
          costMs: '耗时',
          ip: 'IP',
          op: '操作',
          view: '查看',
          empty: '暂无审计记录'
        },
        detail: {
          title: '审计详情',
          basic: '基本信息',
          execution: '执行明细',
          sql: '原始 SQL',
          copy: '复制',
          detail: 'Detail'
        },
        empty: {
          trend: '暂无趋势数据',
          heatmap: '暂无热力图数据'
        },
        copyOk: '已复制',
        exportOk: '已导出 CSV',
        exportFail: '导出失败'
      }
    },
    hr: {
      common: {
        status: '状态',
        form: {
          status: '请选择状态'
        }
      },
      employee: {
        title: '员工列表',
        name: '姓名',
        userName: '用户名',
        employeeNo: '工号',
        email: '邮箱',
        phone: '电话',
        position: '职位',
        avatar: '头像',
        avatarUploadSuccess: '头像上传成功',
        department: '部门',
        tags: '标签',
        form: {
          name: '请输入姓名',
          userName: '请输入用户名(手机号)',
          email: '请输入邮箱',
          phone: '请输入电话',
          position: '请输入职位',
          department: '请选择部门',
          tags: '请选择标签',
          status: '请选择员工状态'
        },
        status: {
          probation: '待转正',
          active: '在职',
          resigned: '已离职'
        },
        transition: {
          toActive: '确认转正',
          toResigned: '办理离职',
          toProbation: '办理返聘',
          resignRemark: '请输入离职备注',
          confirm: '确认变更员工状态吗？',
          success: '员工状态更新成功'
        },
        addEmployee: '新增员工',
        editEmployee: '编辑员工'
      },
      department: {
        title: '部门列表',
        name: '部门名称',
        code: '部门编码',
        manager: '主管',
        description: '描述',
        form: {
          name: '请输入部门名称',
          code: '请输入部门编码',
          manager: '请选择主管',
          description: '请输入描述'
        },
        addDepartment: '新增部门',
        editDepartment: '编辑部门'
      },
      tag: {
        title: '标签列表',
        name: '标签名称',
        category: '分类',
        description: '描述',
        form: {
          name: '请输入标签名称',
          category: '请选择分类',
          description: '请输入描述'
        },
        addTag: '新增标签',
        editTag: '编辑标签'
      },
      my: {
        profileTitle: '个人资料',
        tagTitle: '我的标签',
        colleaguesTitle: '同部门同事',
        editProfile: '编辑我的资料',
        editTags: '编辑我的标签',
        avatarUploadSuccess: '头像上传成功'
      },
      team: {
        title: '下属列表',
        department: '所在部门',
        total: '团队人数',
        statusBreakdown: '状态分布',
        editTags: '编辑标签'
      }
    }
  },
  form: {
    required: '不能为空',
    userName: {
      required: '请输入用户名',
      invalid: '用户名格式不正确'
    },
    phone: {
      required: '请输入手机号',
      invalid: '手机号格式不正确'
    },
    pwd: {
      required: '请输入密码',
      invalid: '密码格式不正确，6-18位字符，包含字母、数字、下划线'
    },
    confirmPwd: {
      required: '请输入确认密码',
      invalid: '两次输入密码不一致'
    },
    code: {
      required: '请输入验证码',
      invalid: '验证码格式不正确'
    },
    email: {
      required: '请输入邮箱',
      invalid: '邮箱格式不正确'
    }
  },
  dropdown: {
    closeCurrent: '关闭',
    closeOther: '关闭其它',
    closeLeft: '关闭左侧',
    closeRight: '关闭右侧',
    closeAll: '关闭所有',
    pin: '固定标签',
    unpin: '取消固定'
  },
  icon: {
    themeConfig: '主题配置',
    themeSchema: '主题模式',
    lang: '切换语言',
    fullscreen: '全屏',
    fullscreenExit: '退出全屏',
    reload: '刷新页面',
    collapse: '折叠菜单',
    expand: '展开菜单',
    pin: '固定',
    unpin: '取消固定'
  },
  datatable: {
    itemCount: '共 {total} 条',
    fixed: {
      left: '左固定',
      right: '右固定',
      unFixed: '取消固定'
    }
  }
};

export default local;
