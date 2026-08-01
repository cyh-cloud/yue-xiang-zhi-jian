# 粤乡智匠 - 项目目录结构

```
粤乡智匠项目/
├── index.html              # 主页面文件
├── case-detail.html        # 案例详情页
├── styles.css              # 样式文件
├── script.js               # 前端交互脚本
├── app.py                  # Flask后端应用
├── run.py                  # 启动脚本
├── test_app.py             # 测试文件
├── requirements.txt        # Python依赖包
└── PROJECT_STRUCTURE.md    # 项目结构说明（本文件）
```

## 文件说明

### 前端文件

1. **index.html**
   - 主页面，包含所有功能模块的HTML结构
   - 响应式设计，支持移动端访问
   - 包含导航栏、各个功能标签页、模态框等

2. **case-detail.html**
   - 成功案例详情独立页面
   - 通过URL参数 `?id=` 接收案例ID
   - 从API获取数据并展示案例背景、发展历程、经验启示等

3. **styles.css**
   - CSS样式文件
   - 采用绿色主题，体现乡村振兴理念
   - 包含动画效果、响应式布局

3. **script.js**
   - 前端交互逻辑
   - 处理导航切换、表单提交、API调用等
   - 包含农时日历、方言交互等功能

### 后端文件

4. **app.py**
   - Flask后端应用主文件
   - 包含所有API端点：
     - 农业技能API
     - 电商运营API
     - 手工技能API
     - 虚拟实训API
     - 本土资源API
     - 就业对接API
     - 教师管理API
     - 用户认证API

5. **run.py**
   - 应用启动脚本
   - 自动打开浏览器
   - 显示启动信息

6. **test_app.py**
   - 单元测试文件
   - 测试各个API端点的功能

7. **requirements.txt**
   - Python依赖包列表
   - 使用pip install -r requirements.txt安装

## 功能模块

### 1. 农业技能培训
- 广东特色农产品选择（荔枝、龙眼、水产等）
- 农时智能日历
- AI农技问答

### 2. 电商运营实训
- 直播带货模拟
- AI话术生成
- 商品文案创作
- 店铺装修指导

### 3. 手工技能传承
- 广绣、潮汕木雕等非遗技艺
- 3D步骤拆解
- 材料采购指南

### 4. 虚拟实训沙盒
- 病虫害AI诊断
- 直播间模拟训练
- AR手工技能指导

### 5. 本土化资源库
- 方言交互支持（粤语、客家话、潮汕话）
- 本地成功案例
- 政策信息推送

### 6. 就业与供应链对接
- 积分激励体系
- 技能证书认证
- 人才供需匹配
- 创业支持服务

### 7. 教师管理
- 学员管理
- 学习数据分析
- 教学报告生成

## 启动方式

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 启动应用
```bash
python run.py
```

### 3. 访问应用
打开浏览器访问: http://localhost:5000

## 演示账户

- **教师账户**: teacher_demo / 123456
- **学员账户**: student_demo / 123456

## 技术栈

### 前端
- HTML5 + CSS3 + JavaScript
- Font Awesome图标库
- 响应式设计

### 后端
- Python Flask
- RESTful API设计
- JSON数据格式

### AI服务
- SiliconFlow API
- Qwen3-32B模型

## 注意事项

1. 首次运行需要安装Python依赖包
2. AI功能需要网络连接
3. 建议使用现代浏览器访问
4. 移动端体验可能有所差异