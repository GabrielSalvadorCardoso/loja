from collections import OrderedDict
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework import generics
from rest_framework import status
from hyper_resource.views import *
from controle_estoque.models import *
from controle_estoque.serializers import *
from controle_estoque.contexts import *

def get_root_response(request):
    format = None
    root_links = {
      'item-list': reverse('controle_estoque:Item_list' , request=request, format=format),
      'produto-list': reverse('controle_estoque:Produto_list' , request=request, format=format),
    }

    ordered_dict_of_link = OrderedDict(sorted(root_links.items(), key=lambda t: t[0]))
    return ordered_dict_of_link

class APIRoot(APIView):

    def __init__(self):
        super(APIRoot, self).__init__()
        self.base_context = BaseContext('api-root')

    def options(self, request, *args, **kwargs):
        context = self.base_context.getContextData(request)
        root_links = get_root_response(request)
        context.update(root_links)
        response = Response(context, status=status.HTTP_200_OK, content_type="application/ld+json")
        response = self.base_context.addContext(request, response)
        return response

    def get(self, request, *args, **kwargs):
        root_links = get_root_response(request)
        response = Response(root_links)
        return self.base_context.addContext(request, response)


class ItemList(CollectionResource):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    contextclassname = 'item-list'
    def initialize_context(self):
        self.context_resource = ItemListContext()
        self.context_resource.resource = self

class ItemDetail(NonSpatialResource):
    serializer_class = ItemSerializer
    contextclassname = 'item-list'
    def initialize_context(self):
        self.context_resource = ItemDetailContext()
        self.context_resource.resource = self

class ProdutoList(CollectionResource):
    queryset = Produto.objects.all()
    serializer_class = ProdutoSerializer
    contextclassname = 'produto-list'
    def initialize_context(self):
        self.context_resource = ProdutoListContext()
        self.context_resource.resource = self

class ProdutoDetail(NonSpatialResource):
    serializer_class = ProdutoSerializer
    contextclassname = 'produto-list'
    def initialize_context(self):
        self.context_resource = ProdutoDetailContext()
        self.context_resource.resource = self

