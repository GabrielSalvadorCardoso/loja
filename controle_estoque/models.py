from __future__ import unicode_literals
from hyper_resource.models import FeatureModel, BusinessModel
# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.

from django.contrib.gis.db import models

class Item(BusinessModel):
    id_item = models.AutoField(primary_key=True)
    n_lote = models.IntegerField()
    id_produto = models.ForeignKey('Produto', models.DO_NOTHING, db_column='id_produto', related_name='itens')

    class Meta:
        managed = False
        db_table = 'item'


class Produto(BusinessModel):
    id_produto = models.AutoField(primary_key=True)
    codigo_bar = models.IntegerField()
    nome = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = 'produto'
