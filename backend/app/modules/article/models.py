"""文章模块的表。

规划中的表：Article（文章）/ Category（分类）/ Tag（标签）/ ArticleTag（多对多关联）。

**铁律一：这里只放本模块的表**，绝不在别的模块的模型上加字段，
也不在这里 import 别的模块的模型。

具体字段在「数据库设计」阶段确定，届时全部继承 app.core.database.Base。
"""
