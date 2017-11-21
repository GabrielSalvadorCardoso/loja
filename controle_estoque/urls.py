from django.conf.urls import include, url
from rest_framework.urlpatterns import format_suffix_patterns
from controle_estoque import views 

urlpatterns = format_suffix_patterns([
    url(r'^$', views.APIRoot.as_view(), name='api_root'),

    url(r'^item-list/(?P<pk>[0-9]+)/$', views.ItemDetail.as_view(), name='Item_detail'),
    url(r'^item-list/(?P<pk>[0-9]+)/(?P<attributes_functions>.*)/$', views.ItemDetail.as_view(), name='Item_detail_af'),
    url(r'^item-list/$', views.ItemList.as_view(), name='Item_list'),
    url(r'^item-list/(?P<attributes_functions>.*)/?$', views.ItemList.as_view(), name='Item_list_af'),

    url(r'^produto-list/(?P<pk>[0-9]+)/$', views.ProdutoDetail.as_view(), name='Produto_detail'),
    url(r'^produto-list/(?P<pk>[0-9]+)/(?P<attributes_functions>.*)/$', views.ProdutoDetail.as_view(), name='Produto_detail_af'),
    url(r'^produto-list/$', views.ProdutoList.as_view(), name='Produto_list'),
    url(r'^produto-list/(?P<attributes_functions>.*)/?$', views.ProdutoList.as_view(), name='Produto_list_af'),

])
