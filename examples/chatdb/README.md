# ChatDB - Text2SQL System（佳欣智能100%自研）

## 后端使用

cd 到 backend 目录下
创建虚拟环境
```angular2html
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

安装依赖
```angular2html

pip install -r requirements.txt

```

初始化数据库
```angular2html
python init_db.py
```

修改.env文件中的相关配置信息(将.env.example复制一份，并重命名为.env)


启动后端服务
```angular2html
uvicorn main:app --reload
```
## 前端使用

cd 到 frontend 目录下
安装依赖
```angular2html
pnpm install
```
启动前端服务
```angular2html
pnpm run dev
```
