import inspect, sys
import os
import re
import django

from django.contrib.gis.db.models.fields import GeometryField
from django.contrib.gis.db import models
from hyper_resource.models import FeatureModel


def is_spatial(model_class):
    """
    Esta função verifica cada um dos campos da classe de modelo passada como argumento.
    Se houver algum campo do tipo GeometryField a função retorna True.
    Caso a função percorra todos os cammpos da classe e não encontre campos GeometryField
    é retornado False indicando que esta classe trata-se de um modelo de negócio comum
    :param model_class:
    :return:
    """

    if isinstance(model_class, models.Model) or isinstance(model_class, FeatureModel):
        for field in model_class._meta.get_fields():
            if isinstance(field, GeometryField):
                return True
    return False

def generate_file(package_name, default_name='models.py'):

    # 'sys.modules' é um dicionário que contém informações de todos os módulos carregados até agora
    # Queremos o módulo que contém nossos modelos então usamos 'controle_estoque.models' como índice do dicionário
    # 'inspect.getmembers()' retorna todos os membros do objeto passado como parâmetro
    # Neste caso ainda foi enviado um critério 'inspect.isclass', para que seja retornado apenas os membros dos objetos que são classes
    # 'classes_from' é uma lista de tuplas. Essas tuplas contem o nome do objeto (o nome da classe, no caso) e o tipo do objeto (tipo class)
    classes_from = inspect.getmembers(sys.modules[package_name + '.models'], inspect.isclass)

    # 'map()' submete cada elemento de uma lista (no caso, 'classes_from') a uma função e retorna uma nova lista com elementos submetidos
    # 'geo_classes' neste caso é uma lista derivada de 'classes_from' apenas com classes que possuem campos do tipo GeometryField
    geo_classes = map(lambda x: x[0], filter(lambda x: is_spatial(x[1]), classes_from)) # ----- PESQUISAR -----

    old_model = default_name
    new_model = default_name+'.new'
    with open(old_model, 'r') as sr: # Abre o arquivo 'models.py' já criado em modo leitura
        with open(new_model, 'w+') as nm: # Cria/abre um arquivo 'models.py.new' em modo escrita
            nm.write('from __future__ import unicode_literals\n')
            nm.write('from hyper_resource.models import FeatureModel, BusinessModel\n') # Adiciona o import das classes de modelo do hyper resource

            # readlines() lê todas as linhas do arquivo e adiciona cada linha do arquivo em uma lista
            for line in sr.readlines():

                # Se a linha lida contiver o import, simplesmente pulamos para próxima linha
                if line == 'from __future__ import unicode_literals\n':
                    continue

                # A cada linha percorrida vemos se a mesma é uma linha que define a classe (com o nome da classe e a herança)
                # Se for a linha que proucuramos, 're.search()' retornará a parte da herança
                # Se não for, simplesmente é retornado 'None'
                # EXPRESSÃO REGULAR: 'class' + 0 ou mais espações em branco + ... + qualquer caracter exceto espaços em branco + (
                # EXPRESSÃO REGULAR: (?P<class_model>.*) indica que tudo que estiver entre 'class' espaço em branco e '('
                # terá 'class_model' como identificador, ou seja, podemos usar "regex.group('class_model')" para nos referenciar aquele trecho da string
                regex_obj = re.search(r'class\s*(?P<class_model>.*)\(', line)

                # 'class_name_in_line' receberá 'None' ou o nome da classe (referenciado por group(1), que tem o mesmo efeito de group('class_model'))
                class_name_in_line = regex_obj if regex_obj is None else regex_obj.group(1)

                # Se 'class_name_in_line', ou seja, o nome da classe esta relacionada na lista de classes com atributos geográficos,
                # então a classe de modelo não herdará mais de 'models.Model' (classe do Django) e sim de 'FeatureModel' (classe do Hyper Resource)
                if class_name_in_line in geo_classes:
                    line = line.replace('models.Model', 'FeatureModel')

                # Se 'class_name_in_line' não for None, ou seja, se 'regex_object' retornar o nome da classe, o modelo passará a herdar de BusinessModel
                elif class_name_in_line is not None:
                    line = line.replace('models.Model', 'BusinessModel')

                # Substituindo todas as linha com ItegerField por AutoField
                elif 'models.IntegerField(primary_key=True)' in line:
                    line = line.replace('models.IntegerField(primary_key=True)', 'models.AutoField(primary_key=True)')

                # Finalmente a linha é escrita no novo arquivo
                nm.write(line)

            nm.close() # Fechando o novo arquivo (que é uma versão modificada do arquivo models.py gerada pelo django)

        sr.close() # Fechando o arquivo models.py gerado pelo django

    os.remove(old_model) # Removendo o models.py gerado pelo django

    os.rename(new_model, old_model) # Renomeando models.py.new (criado nesta função) para o nome do arquivo gerado pelo django (models.py)


# Se este módulo for executado com principal ele gera models.py da aplicação separadamente
if __name__ == "__main__":
    if (len( sys.argv))!= 3:
        print('Usage: python modeler_generator.py django_project_name django_app_name')
        exit()

    prj_name = sys.argv[1]
    app_name = sys.argv[2]
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", prj_name + ".settings")
    django.setup()
    generate_file(app_name)
    print('models.py  has been generated')