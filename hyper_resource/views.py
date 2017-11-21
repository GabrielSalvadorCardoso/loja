import ast
import re
import json

import jwt
import requests

from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.gis.gdal import SpatialReference
from django.db.models.base import ModelBase
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
# Create your views here.
from requests import ConnectionError
from requests import HTTPError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.gis.geos import GEOSGeometry, GeometryCollection
from hyper_resource.contexts import *
from rest_framework.negotiation import BaseContentNegotiation
from django.contrib.gis.db import models
from abc import ABCMeta, abstractmethod


from hyper_resource.models import  FactoryComplexQuery, OperationController, BusinessModel, ConverterType
SECRET_KEY = '-&t&pd%%((qdof5m#=cp-=-3q+_+pjmu(ru_b%e+6u#ft!yb$$'


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    def select_parser(self, request, parsers):
        """
        Select the first parser in the `.parser_classes` list.
        """
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):
        """
        Select the first renderer in the `.renderer_classes` list.
        """
        return (renderers[0], renderers[0].media_type)

class BaseContext(object):

    def __init__(self, contextclassname, serializer_object=None):
        self.serializer_object = serializer_object
        self.contextclassname = contextclassname

    def options(self, request):
        response = Response(self.getContextData(request), status=status.HTTP_200_OK, content_type="application/ld+json")
        response = self.createLinkOfContext(request, response)
        return response

    def addContext(self, request, response):
        return self.createLinkOfContext(request, response)

    def createLinkOfContext(self, request, response, properties=None):
        # if properties is None:
        #     url = reverse('context:detail', args=[self.contextclassname], request=request)
        # else:
        #     url = reverse('context:detail-property', args=[self.contextclassname, ",".join(properties)], request=request)
        url = request.build_absolute_uri()
        url = url if url[-1] != '/' else url[:-1]
        url = url + ".jsonld"

        context_link = ' <'+url+'>; rel=\"http://www.w3.org/ns/json-ld#context\"; type=\"application/ld+json\" '
        if "Link" not in response:
            response['Link'] = context_link
        else:
            response['Link'] += "," + context_link

        return response

    def getHydraData(self, request):
        #classobject = Class.objects.get(name=self.contextclassname)
        #serializerHydra = HydraSerializer(classobject, request)
        return {}

    def addIriTamplate(self, context, request, serializer_object):
        url = request.build_absolute_uri()
        iriTemplate = {
            "@context": "http://www.w3.org/ns/hydra/context.jsonld",
            "@type": "IriTemplate",
            "template": url if url[-1] != '/' else url[:-1] +"{/attribute}",
            "variableRepresentation": "BasicRepresentation",
            "mapping": []
        }
        if serializer_object is not None:
            for attr in serializer_object.Meta.identifiers:
                iriTemplate['mapping'].append({
                    "@type": "IriTemplateMapping",
                    "variable": "attribute",
                    "property": attr,
                    "required": True
                })
        else:
            iriTemplate['mapping'].append({
                "@type": "IriTemplateMapping",
                "variable": "attribute",
                "property": "hydra:supportedProperties",
                "required": True
            })

        context['iriTemplate'] = iriTemplate
        return context

    def getContextData(self, request):
        try:
            classobject = None #Class.objects.get(name=self.contextclassname)
        except:
            return ""
        serializer = None #ContextSerializer(classobject)
        contextdata = {} #serializer.data
        hydradata = self.getHydraData(request)
        if "@context" in hydradata:
            hydradata["@context"].update(contextdata["@context"])
        contextdata.update(hydradata)
        contextdata = self.addIriTamplate(contextdata, request, self.serializer_object)
        return contextdata

class AbstractResource(APIView):
    __metaclass__ = ABCMeta

    serializer_class = None

    def __init__(self):
        super(AbstractResource, self).__init__()
        self.current_object_state = None
        self.object_model = None
        self.name_of_last_operation_executed = None
        self.context_resource = None
        self.initialize_context()
        self.iri_metadata = None
        self.operation_controller = OperationController()
        self.token_need = self.token_is_need()

    content_negotiation_class = IgnoreClientContentNegotiation

    def jwt_algorithm(self):
        return 'HS256'

    def token_is_ok(self, a_token):
        try:
            payload = jwt.decode(a_token, SECRET_KEY, algorithm=self.jwt_algorithm())
            return True
        except jwt.InvalidTokenError:
            return False

    def token_is_need(self):
        return  False

    def dispatch(self, request, *args, **kwargs):
        if self.token_is_need():
            http_auth = 'HTTP_AUTHORIZATION'
            if http_auth in request.META and request.META[http_auth].startswith('Bearer'):
                a_token = request.META['HTTP_AUTHORIZATION'][7:].strip()
                if self.token_is_ok(a_token):
                    return super(AbstractResource, self).dispatch(request, *args, **kwargs)
            return HttpResponse(json.dumps({"token": "token is needed or it is not ok"}), status=401,  content_type='application/json')
        else:
           return  super(AbstractResource, self).dispatch(request, *args, **kwargs)

    #@abstractmethod #Could be override
    def initialize_context(self):
        context_module_name = self.__class__.__module__.split('.')[0] + '.contexts'
        context_module = importlib.import_module(context_module_name)
        context_class_name = self.__class__.__name__ + 'Context'
        context_class = getattr(context_module, context_class_name )
        self.context_resource = context_class()
        self.context_resource.resource = self

    # todo
    def path_request_is_ok(self, a_path):
        return True

    def operations_with_parameters_type(self):
        dic = self.object_model.operations_with_parameters_type()
        return dic

    def model_class(self):
        return self.serializer_class.Meta.model #return self.object_model.model_class()

    def model_class_name(self):
        return self.model_class().__name__

    def attribute_names_to_web(self):
        return self.serializer_class.Meta.fields


    def fields_to_web_for_attribute_names(self, attribute_names):
        fields_model = self.object_model.fields()
        # Poderia ser ModelClass._meta.get_field(field_name) Obs: raise FieldDoesNotExist
        return [field for field in fields_model if field.name in attribute_names ]

    def fields_to_web(self):
        return self.fields_to_web_for_attribute_names(self.attribute_names_to_web())

    def _base_path(self, full_path):
        arr = full_path.split('/')
        ind = arr.index(self.contextclassname)
        return '/'.join(arr[:ind+1])

    def _set_context_to_model(self):
        self.context_resource.contextModel(self.object_model)

    def _set_context_to_attributes(self, attribute_name_array):
        self.context_resource.set_context_to_attributes(attribute_name_array)

    def _set_context_to_only_one_attribute(self, attribute_name):

        self.context_resource.set_context_to_only_one_attribute(self.current_object_state, attribute_name)

    def _set_context_to_operation(self, operation_name):

        self.context_resource.set_context_to_operation(self.current_object_state, operation_name)

    def set_basic_context_resource(self, request ):
        self.context_resource.host = request.META['HTTP_HOST']
        self.context_resource.basic_path = self._base_path(request.META['PATH_INFO'])
        if len(self.kwargs.values()):
            self.context_resource.complement_path = list(self.kwargs.values())[0]
        else:
            self.context_resource.complement_path = ''


    def key_is_identifier(self, key):
        return key in self.serializer_class.Meta.identifiers

    def dic_with_only_identitier_field(self, dict_params):
        dic = dict_params.copy()
        a_dict = {}
        for key, value in dic.items():
            if self.key_is_identifier(key):
                a_dict[key] = value

        return a_dict

    '''
    def get_object(self, arr_of_term=[]):
        first_term = arr_of_term[0]
        if self.is_attribute(self, first_term):
            self.current_object_state =  getattr(self.object_model, first_term, None)
            arr_of_term = arr_of_term[1:]

        for term in arr_of_term:
            self.current_object_state = getattr(self.current_object_state, term, None)
        return  self.current_object_state
    '''
    def attributes_functions_name_template(self):
        return 'attributes_functions'

    def get_object(self, a_dict):
        dicti = self.dic_with_only_identitier_field(a_dict)
        queryset = self.model_class().objects.all()
        obj = get_object_or_404(queryset, **dicti)
        #self.check_object_permissions(self.request, obj)
        return obj

    def put(self, request, *args, **kwargs):
        obj = self.get_object(kwargs)
        serializer = self.serializer_class(obj, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            resp =  Response(status=status.HTTP_204_NO_CONTENT)
            return resp

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        obj = self.get_object(kwargs)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def operation_names_model(self):
        return self.object_model.operation_names()

    def attribute_names_model(self):
        return self.object_model.attribute_names()

    def is_private(self, attribute_or_method_name):
        return attribute_or_method_name.startswith('__') and attribute_or_method_name.endswith('__')

    def is_not_private(self, attribute_or_method_name):
        return not self.is_private(attribute_or_method_name)

    def is_operation(self, operation_name):
        return operation_name in self.operation_names_model()

    def is_attribute(self, attribute_name):
        return self.object_model.is_attribute(attribute_name)

    def is_spatial_attribute(self, attribute_name):
        return False
    def _has_method(self,  method_name):
        return method_name in self.operation_names_model()

    def is_simple_path(self, attributes_functions_str):
        return attributes_functions_str is None or len(attributes_functions_str) == 0

    def path_has_operations(self, attributes_functions_name):
        attrs_functs = attributes_functions_name.split('/')
        operations = self.operation_names_model()
        for att_func in attrs_functs:
            if  att_func in operations:
                return True
        return False

    def path_has_only_attributes(self,  attributes_functions_name):
        attrs_functs = attributes_functions_name.split('/')
        if len(attrs_functs) > 1:
            return False
        if ',' in attrs_functs[0]:
            return True
        if self._has_method(attrs_functs[0]):
            return False
        return self.object_model.is_attribute(attrs_functs[0])

    def transform_path_with_url_as_array(self, arr_of_term):

        arr = []
        http_str = ''
        arr_term =  [ele for ele in arr_of_term if ele != '']

        found_url = False
        size_of_term = len(arr_term)
        for idx, token in enumerate(arr_term):
            if self.token_is_http_or_https_or_www(token.lower()):
                found_url = True

            if  found_url:
                if self.token_is_http_or_https(token):
                   http_str += token + '//'
                elif self.is_end_of_term(token):
                    found_url = False
                    arr.append(http_str)
                    arr.append(token)
                    http_str = ''
                elif (idx == size_of_term -1):
                    found_url = False
                    http_str+= token + '/'
                    arr.append(http_str)
                    http_str = ''

                else:
                   http_str += token + '/'
            else:
                arr.append(token)
        return arr

    def attributes_functions_splitted_by_url(self, attributes_functions_str_url):
        res = attributes_functions_str_url.lower().find('http:')
        if res == -1:
            res = attributes_functions_str_url.lower().find('https:')
            if res == -1:
                res = attributes_functions_str_url.lower().find('www.')
                if res == -1:
                    return [attributes_functions_str_url]

        return [attributes_functions_str_url[0:res], attributes_functions_str_url[res:]]

    def path_has_url(self, attributes_functions_str_url):
        return (attributes_functions_str_url.find('http:') > -1) or (attributes_functions_str_url.find('https:') > -1)\
               or (attributes_functions_str_url.find('www.') > -1)

    def _execute_attribute_or_method(self, object, attribute_or_method_name, array_of_attribute_or_method_name):
        dic = {}
        parameters = []
        if OperationController().is_operation(object, attribute_or_method_name):
            if OperationController().operation_has_parameters(object, attribute_or_method_name):
                parameters = array_of_attribute_or_method_name[0].split('&')
                array_of_attribute_or_method_name = array_of_attribute_or_method_name[1:]
        obj = self._value_from_object(object, attribute_or_method_name, parameters)
        if len(array_of_attribute_or_method_name) == 0:
            return obj

        return self._execute_attribute_or_method(obj, array_of_attribute_or_method_name[0], array_of_attribute_or_method_name[1:])

    def is_operation_and_has_parameters(self, attribute_or_method_name):
        dic = self.operations_with_parameters_type()
        return (attribute_or_method_name in dic) and len(dic[attribute_or_method_name].parameters)



    def function_name(self, attributes_functions_str):
        functions_dic = self.operations_with_parameters_type()
        if str(attributes_functions_str[-1]) in functions_dic:
            return str(attributes_functions_str[-1])
        return str(attributes_functions_str[-2])



    def response_resquest_with_attributes(self,  attributes_functions_name):
        a_dict ={}
        attributes = attributes_functions_name.strip().split(',')
        #self.current_object = self.object_model
        for attr_name in attributes:
           obj = self._value_from_object(self.object_model, attr_name, [])
           a_dict[attr_name] = obj

        self.current_object_state = a_dict
        return (a_dict, 'application/json', self.object_model, {'status': 200})


    def all_parameters_converted(self, attribute_or_function_name, parameters):
        parameters_converted = []
        if self.is_operation_and_has_parameters(attribute_or_function_name):
            parameters_type = self.operations_with_parameters_type()[attribute_or_function_name].parameters
            for i in range(0, len(parameters)):
               parameters_converted.append(parameters_type[i](parameters[i]))


            return parameters_converted

        return self.parametersConverted(parameters)

    def is_attribute_for(self, object, attribute_or_function_name):
        return  hasattr(object, attribute_or_function_name) and not callable(getattr(object, attribute_or_function_name))

    def _value_from_object(self, object, attribute_or_function_name, parameters):

        attribute_or_function_name_striped = attribute_or_function_name.strip()
        self.name_of_last_operation_executed = attribute_or_function_name_striped
        if self.is_attribute_for(object, attribute_or_function_name):
            return getattr(object, attribute_or_function_name_striped)
        if len(parameters)> 0:
            if (isinstance(object, BusinessModel) or isinstance(object, GEOSGeometry)):
                params = self.all_parameters_converted(attribute_or_function_name_striped, parameters)
            else:
                params = ConverterType().convert_parameters(type(object), attribute_or_function_name, parameters)
            return getattr(object, attribute_or_function_name_striped)(*params)
        return getattr(object, attribute_or_function_name_striped)()

    def parametersConverted(self, params_as_array):
        paramsConveted = []

        for value in params_as_array:
            if value.lower() == 'true':
                paramsConveted.append(True)
                continue
            elif value.lower() == 'false':
                paramsConveted.append(False)
                continue

            try:
                paramsConveted.append(int( value ) )
                continue
            except ValueError:
                pass
            try:
               paramsConveted.append( float( value ) )
               continue
            except ValueError:
                pass
            try:
               paramsConveted.append( GEOSGeometry( value ) )
               continue
            except ValueError:
                pass
            try:
                http_str = (value[0:4]).lower()
                if (http_str == 'http'):
                    resp = requests.get(value)
                    if 400 <= resp.status_code <= 599:
                        raise HTTPError({resp.status_code: resp.reason})
                    js = resp.json()

                    if (js.get("type") and js["type"].lower() in ['feature', 'featurecollection']):
                        a_geom = js["geometry"]
                    else:
                        a_geom = js
                    paramsConveted.append(GEOSGeometry((json.dumps(a_geom))))
            except (ConnectionError,  HTTPError) as err:
                print('Error: '.format(err))
                #paramsConveted.append (value)

        return paramsConveted

class NonSpatialResource(AbstractResource):

    def response_of_request(self,  attributes_functions_str):
        att_funcs = attributes_functions_str.split('/')
        if (not self.is_operation(att_funcs[0])) and self.is_attribute(att_funcs[0]):
            att_funcs = att_funcs[1:]

        self.current_object_state = self._execute_attribute_or_method(self.object_model, att_funcs[0], att_funcs[1:])

        if hasattr(self.current_object_state, 'model') and issubclass(self.current_object_state.model, Model):
            class_name = self.current_object_state.model.__name__ + 'Serializer'
            serializer_cls = self.object_model.class_for_name(self.serializer_class.__module__, class_name)
            if isinstance(self.current_object_state, QuerySet):
                self.current_object_state = serializer_cls(self.current_object_state, many=True,
                                                           context={'request': self.request}).data
            elif isinstance(self.current_object_state.field, OneToOneField):
                self.current_object_state = serializer_cls(self.current_object_state, context={'request': self.request}).data
            else:
                self.current_object_state = serializer_cls(self.current_object_state, many=True, context={'request': self.request}).data

        a_value = {self.name_of_last_operation_executed: self.current_object_state}

        return (a_value, 'application/json', self.object_model, {'status': 200})

    def basic_get(self, request, *args, **kwargs):

        self.object_model = self.get_object(kwargs)
        self.current_object_state = self.object_model
        self.set_basic_context_resource(request)
        # self.request.query_params.
        attributes_functions_str = kwargs.get(self.attributes_functions_name_template())

        if self.is_simple_path(attributes_functions_str):

            serializer = self.serializer_class(self.object_model, context={'request': self.request})
            output = (serializer.data, 'application/json', self.object_model, {'status': 200})

        elif self.path_has_only_attributes(attributes_functions_str):
            output = self.response_resquest_with_attributes(attributes_functions_str.replace(" ", ""))
            dict_attribute = output[0]
            if len(attributes_functions_str.split(',')) > 1:
                self._set_context_to_attributes(dict_attribute.keys())
            else:
                self._set_context_to_only_one_attribute(attributes_functions_str)
        elif self.path_has_url(attributes_functions_str.lower()):
            output = self.response_request_attributes_functions_str_with_url( attributes_functions_str)
            self.context_resource.set_context_to_object(self.current_object_state, self.name_of_last_operation_executed)
        else:
            output = self.response_of_request(attributes_functions_str)
            self._set_context_to_operation(self.name_of_last_operation_executed)

        return output

    def get(self, request, *args, **kwargs):

        dict_for_response = self.basic_get(request, *args, **kwargs)
        status = dict_for_response[3]['status']
        if status in [400, 401,404]:
            return Response({'Error ': 'The request has problem. Status:' + str(status)}, status=status)

        if status in [500]:
           return Response({'Error ': 'The server can not process this request. Status:' + str(status)}, status=status)

        accept = request.META['HTTP_ACCEPT']


        return Response(data=dict_for_response[0], content_type=dict_for_response[1])

    def options(self, request, *args, **kwargs):
        self.basic_get(request, *args, **kwargs)
        #return self.context_resource.context()
        return Response ( data=self.context_resource.context(), content_type='application/ld+json' )

class StyleResource(AbstractResource):
    pass

class SpatialResource(AbstractResource):

    def __init__(self):
        super(SpatialResource, self).__init__()
        self.iri_style = None
    # Must be override
    def initialize_context(self):
        pass

    def get_geometry_object(self, object_model):
        return getattr(object_model, self.geometry_field_name(), None)

    def geometry_field_name(self):
        return self.serializer_class.Meta.geo_field

    def make_geometrycollection_from_featurecollection(self, feature_collection):
        geoms = []
        features = json.loads(feature_collection)
        for feature in features['features']:
            feature_geom = json.dumps(feature['geometry'])
            geoms.append(GEOSGeometry(feature_geom))
        return GeometryCollection(tuple(geoms))

    def all_parameters_converted(self, attribute_or_function_name, parameters):
        parameters_converted = []
        if self.is_operation_and_has_parameters(attribute_or_function_name):
            parameters_type = self.operations_with_parameters_type()[attribute_or_function_name].parameters
            for i in range(0, len(parameters)):
                if GEOSGeometry == parameters_type[i]:
                    if not (parameters[i][0] == '{' or parameters[i][0] == '['):
                        parameters_converted.append(GEOSGeometry(parameters[i]))

                    else:
                        geometry_dict = json.loads(parameters[i])

                        if isinstance(geometry_dict, dict) and geometry_dict['type'].lower() == 'feature':
                            parameters_converted.append(parameters_type[i](json.dumps(geometry_dict['geometry'])))
                        elif isinstance(geometry_dict, dict) and geometry_dict['type'].lower() == 'featurecollection':
                            geometry_collection = self.make_geometrycollection_from_featurecollection(parameters[i])
                            parameters_converted.append(parameters_type[i](geometry_collection))
                        else:
                            parameters_converted.append(parameters_type[i](parameters[i]))
                else:
                    parameters_converted.append(parameters_type[i](parameters[i]))


            return parameters_converted

        return self.parametersConverted(parameters)

    def _value_from_objectOLD(self, object, attribute_or_function_name, parameters):

        attribute_or_function_name_striped = attribute_or_function_name.strip()
        self.name_of_last_operation_executed = attribute_or_function_name_striped
        if len(parameters):
            params = self.all_parameters_converted(attribute_or_function_name_striped, parameters)
            return getattr(object, attribute_or_function_name_striped)(*params)

        return getattr(object, attribute_or_function_name_striped)

    def parametersConverted(self, params_as_array):
        paramsConveted = []

        for value in params_as_array:
            if value.lower() == 'true':
                paramsConveted.append(True)
                continue
            elif value.lower() == 'false':
                paramsConveted.append(False)
                continue

            try:
                paramsConveted.append(int( value ) )
                continue
            except ValueError:
                pass
            try:
               paramsConveted.append( float( value ) )
               continue
            except ValueError:
                pass
            try:
               paramsConveted.append( GEOSGeometry( value ) )
               continue
            except ValueError:
                pass
            try:
                http_str = (value[0:4]).lower()
                if (http_str == 'http'):
                    resp = requests.get(value)
                    if 400 <= resp.status_code <= 599:
                        raise HTTPError({resp.status_code: resp.reason})
                    js = resp.json()

                    if (js.get("type") and js["type"].lower() in ['feature', 'featurecollection']):
                        a_geom = js["geometry"]
                    else:
                        a_geom = js
                    paramsConveted.append(GEOSGeometry((json.dumps(a_geom))))
            except (ConnectionError,  HTTPError) as err:
                print('Error: '.format(err))
                #paramsConveted.append (value)

        return paramsConveted

    def dict_as_geojson(self, a_dict):
        d = {}
        d["type"] = "Feature"
        d["geometry"] = a_dict[self.geometry_field_name()]
        a_dict.pop(self.geometry_field_name(), None)
        d["properties"] = a_dict
        return d

    def response_resquest_with_attributes(self,  attributes_functions_name):
        a_dict ={}
        attributes = attributes_functions_name.strip().split(',')

        #self.current_object = self.object_model
        for attr_name in attributes:
           obj = self._value_from_object(self.object_model, attr_name, [])
           if isinstance(obj, GEOSGeometry):
               geom = obj
               obj = json.loads(obj.geojson)
               if len(attributes) == 1:
                   return (obj, 'application/vnd.geo+json', geom, {'status': 200})
           a_dict[attr_name] = obj
        if self.geometry_field_name() in attributes:
            a_dict = self.dict_as_geojson(a_dict)
        self.current_object_state = a_dict

        return (a_dict, 'application/json', self.object_model, {'status': 200})

    def response_request_attributes_functions_str_with_url(self, attributes_functions_str):
        attributes_functions_str = re.sub(r':/+', '://', attributes_functions_str)
        arr_of_two_url = self.attributes_functions_splitted_by_url(attributes_functions_str)
        resp = requests.get(arr_of_two_url[1])
        if resp.status_code in[400, 401, 404]:
            return ({},'application/json', self.object_model, {'status': resp.status_code})
        if resp.status_code == 500:
            return ({},'application/json', self.object_model,{'status': resp.status_code})
        j = resp.text
        attributes_functions_str = arr_of_two_url[0] + j

        return self.response_of_request(attributes_functions_str)

    def response_of_request(self,  attributes_functions_str):
        att_funcs = attributes_functions_str.split('/')

        #obj = self.get_geometry_object(self.object_model)

       # if (not self.is_operation(att_funcs[0])) and self.is_attribute(att_funcs[0]):
        #    att_funcs = att_funcs[1:]

        self.current_object_state = self._execute_attribute_or_method(self.object_model, att_funcs[0], att_funcs[1:])
        a_value = self.current_object_state
        if isinstance(a_value, GEOSGeometry):
            geom = a_value
            a_value = json.loads(a_value.geojson)
            return (a_value, 'application/vnd.geo+json', geom, {'status': 200})
        elif isinstance(a_value, SpatialReference):
           a_value = { self.name_of_last_operation_executed: a_value.pretty_wkt}
        elif isinstance(a_value, memoryview):
            return (a_value, 'application/octet-stream', self.object_model, {'status': 200})
        else:
            a_value = {self.name_of_last_operation_executed: a_value}

        return (a_value, 'application/json', self.object_model, {'status': 200})

class FeatureResource(SpatialResource):

    def __init__(self):
        super(FeatureResource, self).__init__()

    # Must be override
    def initialize_context(self):
        pass

    def is_spatial_attribute(self, attribute_name):
        return self.model.geo_field_name() == attribute_name.lower()

    def operations_with_parameters_type(self):

        dic = self.object_model.operations_with_parameters_type()

        return dic

    def basic_get(self, request, *args, **kwargs):

        self.object_model = self.get_object(kwargs)
        self.current_object_state = self.object_model
        self.set_basic_context_resource(request)
        # self.request.query_params.
        attributes_functions_str = kwargs.get(self.attributes_functions_name_template())

        if self.is_simple_path(attributes_functions_str):
            serializer = self.serializer_class(self.object_model)
            output = (serializer.data, 'application/vnd.geo+json', self.object_model, {'status': 200})

        elif self.path_has_only_attributes(attributes_functions_str):
            output = self.response_resquest_with_attributes(attributes_functions_str.replace(" ", ""))
            dict_attribute = output[0]
            if len(attributes_functions_str.split(',')) > 1:
                self._set_context_to_attributes(dict_attribute.keys())
            else:
                self._set_context_to_only_one_attribute(attributes_functions_str)
        elif self.path_has_url(attributes_functions_str.lower()):
            output = self.response_request_attributes_functions_str_with_url( attributes_functions_str)
            self.context_resource.set_context_to_object(self.current_object_state, self.name_of_last_operation_executed)
        else:
            s = str(attributes_functions_str)
            if s[-1] == '/':
               s = s[:-1]
            output = self.response_of_request(s)
            self._set_context_to_operation(self.name_of_last_operation_executed)

        return output

    def get(self, request, *args, **kwargs):

        dict_for_response = self.basic_get(request, *args, **kwargs)
        status = dict_for_response[3]['status']
        if status in [400, 401,404]:
            return Response({'Error ': 'The request has problem. Status:' + str(status)}, status=status)

        if status in [500]:
           return Response({'Error ': 'The server can not process this request. Status:' + str(status)}, status=status)

        accept = request.META['HTTP_ACCEPT']
        if accept.lower() == "image/png" or kwargs.get('format', None) == 'png':
            if len(dict_for_response) == 3:
                queryset = dict_for_response[2]
                image = self.get_png(queryset, request)
                # headers = response._headers
                return HttpResponse(image, content_type="image/png")
                # headers.update(response._headers)
                # response._headers = headers
            else:
                return Response({'Erro': 'The server can generate an image only from a geometry data'},
                                status=status.HTTP_404_NOT_FOUND)
        if dict_for_response[1] =='application/octet-stream':
            return HttpResponse(dict_for_response[0], content_type='application/octet-stream')
        return Response(data=dict_for_response[0], content_type=dict_for_response[1])

    def options(self, request, *args, **kwargs):
        self.basic_get(request, *args, **kwargs)
        #return self.context_resource.context()
        return Response ( data=self.context_resource.context(), content_type='application/ld+json' )

class AbstractCollectionResource(AbstractResource):
    def __init__(self):
        super(AbstractCollectionResource, self).__init__()
        self.queryset = None


    def token_is_http_or_https(self, token):
        return  token.lower() in ['http:', 'https:']

    def token_is_http(self, token):
        return 'http:' == token

    def token_is_https(self, token):
        return 'https:' == token

    def token_is_www(self, token):
        return True if token.find('www.') > -1 else False

    def token_is_http_or_https_or_www(self, token):
        return  self.token_is_http_or_https(token) or self.token_is_www(token)

    def logical_operators(self):
        return FactoryComplexQuery().logical_operators()

    def attributes_functions_str_is_filter_with_spatial_operation(self, attributes_functions_str):

        arr_str = attributes_functions_str.split('/')[1:]

        geom_ops = self.operation_controller.geometry_operations_dict()

        for str in arr_str:
            if self.is_spatial_attribute(str):
              ind = arr_str.index(str)
              if ind +1 <= len(arr_str):
                return arr_str[ind + 1] in geom_ops()

        return False

    def path_has_filter_operation(self, attributes_functions_str):
        att_funcs = attributes_functions_str.split('/')
        return len(att_funcs) > 1 and  (att_funcs[0].lower() == 'filter')

    def path_has_map_operation(self, attributes_functions_str):
        att_funcs = attributes_functions_str.split('/')
        return len(att_funcs) > 1 and (att_funcs[0].lower() == 'map')


    def q_object_for_filter_array_of_terms(self, array_of_terms):
        return FactoryComplexQuery().q_object_for_filter_expression(None, self.model_class(), array_of_terms)

    def q_object_for_filter_expression(self, attributes_functions_str):
        arr = attributes_functions_str.split('/')

        if self.path_has_url(attributes_functions_str):
           arr = self.transform_path_with_url_as_array(arr)

        return self.q_object_for_filter_array_of_terms(arr[1:])

    def get_objects_from_filter_operation(self, attributes_functions_str):
        q_object = self.q_object_for_filter_expression(attributes_functions_str)
        return self.model_class().objects.filter(q_object)

    def get_objects_from_map_operation(self, attributes_functions_str):
        q_object = self.q_object_for_filter_expression(attributes_functions_str)
        return self.model_class().objects.filter(q_object)

    def operation_names_model(self):
        return self.operation_controller.collection_operations_dict()

    @abstractmethod  # Must be override
    def basic_get(request, *args, **kwargs):
        pass

    def get(self, request, *args, **kwargs):

        basic_response = self.basic_get(request, *args, **kwargs)
        return Response(data=basic_response["data"],status=basic_response["status"], content_type=basic_response["content_type"])

    def options(self, request, *args, **kwargs):
        self.basic_get(request, *args, **kwargs)
        #return self.context_resource.context()
        return Response ( data=self.context_resource.context(), content_type='application/ld+json' )

    def basic_post(self, request):
        response =  Response(status=status.HTTP_201_CREATED, content_type='application/json')
        response['Content-Location'] = request.path + str(self.object_model.pk)
        return response

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if serializer.is_valid():
            obj =  serializer.save()
            self.object_model = obj
            return self.basic_post(request)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CollectionResource(AbstractCollectionResource):

    def operations_with_parameters_type(self):
        return self.operation_controller.collection_operations_dict()

    def get_objects_serialized(self):
        objects = self.model_class().objects.all()
        return self.serializer_class(objects, many=True, context={'request': self.request}).data

    def get_objects_serialized_by_only_attributes(self, attribute_names_str):
        arr = []
        attribute_names_str_as_array = attribute_names_str.split(',')

        values = self.model_class().objects.values(*attribute_names_str_as_array)
        for dic in values:
            a_dic = {}
            for att_name in attribute_names_str_as_array:
                a_dic[att_name] = dic[att_name]
                arr.append(a_dic)
        return arr

    def get_objects_serialized_by_functions(self, attributes_functions_str):

        objects = []
        if self.path_has_filter_operation(attributes_functions_str):
            objects = self.get_objects_from_filter_operation(attributes_functions_str)

        return self.serializer_class(objects, many=True, context={'request': self.request}).data

    def basic_get(self, request, *args, **kwargs):
        self.object_model = self.model_class()()
        self.set_basic_context_resource(request)
        attributes_functions_str = self.kwargs.get("attributes_functions", None)

        if self.is_simple_path(attributes_functions_str):  # to get query parameters
            return {"data": self.get_objects_serialized(),"status": 200, "content_type": "application/json"}

        elif self.path_has_only_attributes(attributes_functions_str):
            return {"data": self.get_objects_serialized_by_only_attributes(attributes_functions_str),"status": 200, "content_type": "application/json"}


        elif self.path_has_operations(attributes_functions_str) and self.path_request_is_ok(attributes_functions_str):
            return {"data": self.get_objects_serialized_by_functions(attributes_functions_str),"status": 200, "content_type": "application/json"}

        else:
            return {"data": "This request has invalid attribute or operation","status": 400, "content_type": "application/json"}


class SpatialCollectionResource(AbstractCollectionResource):

    #To do
    def path_request_is_ok(self, attributes_functions_str):
        return True

    def geometry_field_name(self):
        return self.serializer_class.Meta.geo_field

    def operation_names_model(self):
        return self.operation_controller.feature_collection_operations_dict().keys()

    def path_has_only_spatial_operation(self, attributes_functions_str):
        pass

class FeatureCollectionResource(SpatialCollectionResource):

    def geometry_operations(self):
        return self.operation_controller.geometry_operations_dict()

    def geometry_field_name(self):
        return self.serializer_class.Meta.geo_field

    def is_spatial_attribute(self, attribute_name):
        return attribute_name == self.geometry_field_name()

    def is_spatial_operation(self, operation_name):
        return operation_name in self.geometry_operations()

    def path_has_only_spatial_operation(self, attributes_functions_str):

        att_funcs = attributes_functions_str.split('/')
        spatial_operation_names = self.geometry_operations().keys()

        if (len(att_funcs) > 1 and (att_funcs[0].lower() in spatial_operation_names)):
           return True

        return  (att_funcs[1].lower() in spatial_operation_names)

    def is_filter_with_spatial_operation(self, attributes_functions_str):
        att_funcs = attributes_functions_str.split('/')
        return (len(att_funcs) > 1 and (att_funcs[0].lower() in self.geometry_operations().keys())) or self.attributes_functions_str_is_filter_with_spatial_operation(attributes_functions_str)

    def operations_with_parameters_type(self):
        return self.operation_controller.feature_collection_operations_dict()

    def get_objects_serialized(self):
        objects = self.model_class().objects.all()
        return self.serializer_class(objects, many=True).data

    def get_objects_from_spatial_operation(self, array_of_terms):
        q_object = self.q_object_for_filter_array_of_terms(array_of_terms)
        return self.model_class().objects.filter(q_object)

    def is_end_of_term(self, term):
        return term in self.logical_operators()

    def inject_geometry_attribute_in_spatial_operation_for_path(self, arr_of_term):
        indexes = []
        for idx, term in enumerate(arr_of_term):
            if term in self.geometry_operations():
                indexes.append(idx)
        count = 0
        for i in indexes:
            arr_of_term.insert(i + count, self.geometry_field_name())
            count+=1

        return arr_of_term

    def path_has_geometry_attribute(self, term_of_path):
        return term_of_path.lower() == self.geometry_field_name()

    def get_objects_with_spatial_operation_serialized(self, attributes_functions_str):
        att_func_arr = attributes_functions_str.split('/')
        arr = att_func_arr
        if self.is_spatial_operation(att_func_arr[0]) and not self.path_has_geometry_attribute(att_func_arr[0]):
            if self.path_has_url(attributes_functions_str):
                arr = self.transform_path_with_url_as_array(att_func_arr)
            arr = self.inject_geometry_attribute_in_spatial_operation_for_path(arr)
        objects = self.get_objects_from_spatial_operation(arr)
        return self.serializer_class(objects, many=True).data

    def get_objects_serialized_by_only_attributes(self, attribute_names_str):
        arr = []
        attribute_names_str_as_array = attribute_names_str.split(',')

        values = self.model_class().objects.values(*attribute_names_str_as_array)
        for dic in values:
            a_dic = {}
            for att_name in attribute_names_str_as_array:
                a_dic[att_name] = dic[att_name] if not isinstance(dic[att_name], GEOSGeometry) else json.loads(dic[att_name].json)
                arr.append(a_dic)
        return arr


    def get_objects_serialized_by_functions(self, attributes_functions_str):

        objects = []
        if self.path_has_filter_operation(attributes_functions_str) or self.path_has_spatial_operation(attributes_functions_str) or  self.is_filter_with_spatial_operation(attributes_functions_str):
            objects = self.get_objects_from_filter_operation(attributes_functions_str)
        elif self.path_has_map_operation(attributes_functions_str):
            objects = self.get_objects_from_map_operation(attributes_functions_str)

        return self.serializer_class(objects, many=True).data

    def basic_response(self, request, model_object):
        response = Response(status=status.HTTP_201_CREATED, content_type='application/geojson')
        response['Content-Location'] = request.path + str(model_object.id)
        return response

    def basic_get(self, request, *args, **kwargs):
        self.object_model = self.model_class()()
        self.set_basic_context_resource(request)
        attributes_functions_str = self.kwargs.get("attributes_functions", None)

        if self.is_simple_path(attributes_functions_str):  # to get query parameters
            return {"data": self.get_objects_serialized(),"status": 200, "content_type": "application/json"}

        elif self.path_has_only_attributes(attributes_functions_str):
            return {"data": self.get_objects_serialized_by_only_attributes(attributes_functions_str),"status": 200, "content_type": "application/json"}

        #elif self.path_has_url(attributes_functions_str.lower()):
        #    pass
        elif self.path_has_only_spatial_operation(attributes_functions_str):
            return {"data": self.get_objects_with_spatial_operation_serialized(attributes_functions_str), "status": 200,
                    "content_type": "application/json"}

        elif self.path_has_operations(attributes_functions_str) and self.path_request_is_ok(attributes_functions_str):
            return {"data": self.get_objects_serialized_by_functions(attributes_functions_str),"status": 200, "content_type": "application/json"}

        else:
            return {"data": "This request has invalid attribute or operation","status": 400, "content_type": "application/json"}


