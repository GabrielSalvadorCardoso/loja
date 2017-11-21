from django.conf.urls import include, url
urlpatterns = [

    url(r'^controle_estoque-list/',include('controle_estoque.urls',namespace='controle_estoque')),


]
urlpatterns += [

    url(r'^api-auth/', include('rest_framework.urls',namespace='rest_framework')),

]


