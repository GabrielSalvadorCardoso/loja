from controle_estoque.models import *
from hyper_resource.serializers import *
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from rest_framework.serializers import HyperlinkedRelatedField

class ItemSerializer(BusinessSerializer):
    id_produto = HyperlinkedRelatedField(view_name='controle_estoque:Produto_detail', many=False, read_only=True)
    class Meta:
        model = Item
        fields = ['id_item','n_lote','id_produto']
        identifier = 'id_item'
        identifiers = ['pk', 'id_item']

    def field_relationship_to_validate_dict(self):
        a_dict = {}
        # Indica, na validação deste objeto, que e dependente da existência  de outro
        # Repare que o valor do índice deste dicionário tem exatamente o mesmo nome da foreign key representada por HyperlinkedRelatedField acima
        a_dict['id_produto_id'] = 'id_produto'
        return a_dict

class ProdutoSerializer(BusinessSerializer):
    itens = HyperlinkedRelatedField(view_name="controle_estoque:Item_detail", many=True, read_only=True)

    class Meta:
        model = Produto
        fields = ['id_produto','codigo_bar','nome', 'itens']
        identifier = 'id_produto'
        identifiers = ['pk', 'id_produto']



serializers_dict = {}