import os
import sys, inspect
import django
from django.contrib.gis.db import models
from django.contrib.gis.db.models import GeometryField
from django.db.models import ForeignKey, ManyToOneRel

from django.contrib.gis.db.models.fields import GeometryField

from hyper_resource.models import FeatureModel


def is_spatial(model_class):
    if isinstance(model_class, models.Model) or isinstance(model_class, FeatureModel):
        for field in model_class._meta.get_fields():
            if isinstance(field, GeometryField):
                return True

    return False
def generate_snippet_field_relationship_to_validate_dict(field_names):
    """
    Esta função é responsável por criar a função de validação por foreign key
    do serializer correspondente com o dicionário de validação
    :param field_names:
    :return:
    """

    new_str = ''
    new_str = (" " * 4) + "def field_relationship_to_validate_dict(self):\n" # Função para validar o objeto
    new_str += (' ' * 8) + "a_dict = {}\n" # criando um dicionario

    for field_name in field_names: # Itera sobre cada uma das ForeignKeys
         # Cada uma das foreign keys terá a_dict['NOME_CAMPO_FOREIGN_KEY_id'] = 'NOME_CAMPO_FOREIGN_KEY'
         new_str += (" " * 8) + "a_dict[" + "'" +field_name + '_id' +"'] = " + "'" + field_name + "'\n"

    new_str += (" " * 8) + "return a_dict\n" # Retorna o dicionario

    return new_str

def generate_snippets_to_serializer(package_name, model_class_name, model_class):
    """
    Gera a classe serializer do modelo 'model_class' com seus respectivos atributos
    como uma lista a ser serializada (lista contida a metaclasse do serializer).
    Gera e serializa os campos ForeignKey (que não são serializados altomaticamente
    pelo django rest framework)
    :param package_name:
    :param model_class_name:
    :param model_class:
    :return:
    """

    arr = [] # Esta será a lista de linhas (ou concatenação de strings) que será inserida no serializers.py
    field_names_fk = []

    # Define a herança da classe baseando-se se a classe possui atributos geométricos ou não
    if is_spatial(model_class):
        class_name = 'Serializer(GeoBusinessSerializer)'
    else:
        class_name = 'Serializer(BusinessSerializer)'

    # Contatena strings para formar a linha de definição da classe e adiciona a lista de linhas
    arr.append('class ' +model_class_name + class_name+':\n')

    for field in model_class._meta.get_fields(): # Itera sobre todos os campos da classe de modelo
        if isinstance(field, ForeignKey): # Se o campo representa uma foreign key
            field_names_fk.append(field.name) # Armazena o nome do campo foreign key na lista

            # 'view_name' será o nome da classe a qual o campo foreign key esta relacionado
            view_name = type(field.related_model()).__name__ + "_detail"

            # O campo do modelo se torna o campo do serializer (field.name retorna o nome do campo do modelo)
            # Toda ForeignKey do modelo irá virar uma HyperlinkedRelatedField no serializer
            # Resultado:    campo_modelo = HyperlinkedRelatedField(view_name='controle_estoque:RELATED_VIEW_MODEL_detail ... )'
            arr.append((' ' * 4) + field.name+" = HyperlinkedRelatedField(view_name='"+package_name +':'+view_name+"', many=False, read_only=True)\n")

        elif isinstance(field, ManyToOneRel) and field.related_name is not None: # Se o campo representa uma ForeignKey(many=True)
            # 'view_name' será o nome do modelo relacionado a este campo + _detail
            view_name = type(field.related_model()).__name__ + "_detail" #view_name = field.name + "_detail"
            # Resultado:    NOME_CAMPO_MODELO = HyperlinkedRelatedField(view_name=NOME_PACOTE_DO_APP:VIEW_RELACIONADA_CAMPO_detail ... )
            arr.append((
                       ' ' * 4) + field.name + " = HyperlinkedRelatedField(view_name='" +package_name +':'+ view_name + "', many=True, read_only=True)\n")

    arr.append((' ' * 4) + 'class Meta:\n') # Adicionando a Metaclass a lista de linhas do serializer
    arr.append((' ' * 8) + 'model = ' +model_class_name + '\n') # Indicando na metaclasse o modelo a ser serializado

    # Os campos 'identifier' e 'geo_field' do serializer são None por padrão
    identifier = None
    geom = None

    fields = model_class._meta.get_fields() # Retorna todos os campos da classe de modelo
    arr.append((' ' * 8) + 'fields = [') # Iniciando a lista a ser serializada
    for i, field in enumerate(fields):
        # Se o campo for um ForeignKey(many=True) e o campo não for relacionado a outro modelo (ForeignKey(related_name=None))
        # Não serializamos
        if isinstance(field, ManyToOneRel) and field.related_name is None:
            continue

        arr.append("'" + field.name + "'") # colocando o nome do campo do modelo na lista de campos serializados

        if i < len(fields) - 1: # Se este campo for o penúltimo (ou anterior), adicionamos uma vírgula a lista
            arr.append(',')
        else: # Se for o último, fechamos a lista
            arr.append(']\n')

        # Se este campo do modelo tiver uma atributo chamado 'primary_key' E for uma chave primaria (não seria OU?) ...
        if hasattr(field, 'primary_key') and field.primary_key:
            identifier = field.name # ... então este campo será o identificador na mataclasse do serializer

        if isinstance(field, GeometryField): # Se este campo for um campo geométrico ...
            geom = field.name # ... então esta campo será o valor do atributo 'geo_field' da metaclasse do serializer

    if geom is not None: # Se tiver algum campo geométrico, este será adicionado como valor do atributos 'geo_field' da metaclasse do serializer
        arr.append((' ' * 8) + "geo_field = '" + geom + "'\n")

    arr.append((' ' * 8) + "identifier = '" + identifier + "'\n") # Configura o campo 'identifier' da metaclasse do serializer
    arr.append((' ' * 8) + "identifiers = ['pk', " + "'" + identifier + "'"+ "]\n") # Configura uma lista 'identifiers' com 'pk' e o identificador

    if len(field_names_fk) > 0: # Se existrirem ForeignKey's neste model ...
        arr.append("\n")
        # Envia a lista de ForeignKey para que seja criado um dicionário de validação baseado nelas
        arr.append(generate_snippet_field_relationship_to_validate_dict(field_names_fk))

    arr.append("\n")

    return arr # Retorna a lista com as linha de código para adicionar em 'serializers.py'
    # Nesta altura 'arr' já é composto pelos imports do serializers.py e a classe serializer correspondente de cada model
    # Cada serializer possui HyperlinkedRelatedField (se for o caso), a classe Meta, a lista de campos para serializar (fields = [])
    # os atributos identifier, identifiers e geo_field (se for o caso)
    # Ainda possui a função field_relationship_to_validate_dict() que retorna um dicionário com as foreign key que precisam ser validadas antes da criação do objeto


def generate_file(package_name, default_name= '\serializers.py'):
    """
    Esta função é responsável por gerar o arquivo 'serializers.py' referente
    aos models encontrados em 'models.py' do referido app (package_name). Esta
    função gera os import necessários e a função 'generate_snippets_to_serializer()'
    gera um ModelSerializer para cada modelo presente em 'models.py'
    :param package_name:
    :param default_name:
    :return:
    """

    # Retornando todos os membros de 'controle_estoque.models' que são classes
    # cujo nome não seja BusinessModel nem FeatureModel e seja instancia de ModelBase (não seria subclasse de ModelBase?)
    # Ou seja, 'classes_from' é uma lista de classes (nome e tipo) derivadas de ModelBase (no caso, todas as classes do models.py)
    classes_from = [(name, method) for name, method in  inspect.getmembers(sys.modules[package_name + '.models'],inspect.isclass)  if (name != 'BusinessModel' and name != 'FeatureModel' and isinstance(method, django.db.models.base.ModelBase)) ]

    with open(default_name, 'w+') as sr:
        sr.write("from "+package_name+".models import *\n")
        sr.write("from hyper_resource.serializers import *\n")
        sr.write("from rest_framework_gis.serializers import GeoFeatureModelSerializer\n\n")
        sr.write("from rest_framework.serializers import HyperlinkedRelatedField\n\n")

        for model_class_arr in classes_from: # Iterando sobre cada uma das classes da lista
            # 'model_class_arr[0]' é o nome da classe, 'model_class_arr[1]' é o tipo
            # generate_snippets_to_serializer() irá criar um serializer para cada classe de modelo
            for snippet in generate_snippets_to_serializer(package_name, model_class_arr[0], model_class_arr[1]):
                sr.write(snippet) # Finalmente todos os serializer são escritos no arquivo

        sr.write('\n\n')
        sr.write('serializers_dict = {}')
        sr.close()

if __name__ == "__main__":
    if (len(sys.argv)) != 3:
        print('Usage: python serializer_generator.py django_project_name django_app_name')
        exit()
    prj_name = sys.argv[1]
    app_name = sys.argv[2]
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", prj_name + ".settings")
    django.setup()
    generate_file(app_name)
    print('serializers.py  has been generated')