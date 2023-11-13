import time
import logging
import requests
import json

from ariadne import (QueryType,
                    MutationType, 
                    SubscriptionType, 
                    ObjectType, 
                    make_executable_schema, 
                    load_schema_from_path)

from ariadne.asgi import GraphQL
from ariadne.asgi.handlers import GraphQLTransportWSHandler
from broadcaster import Broadcast
from starlette.applications import Starlette
from graphql.type import GraphQLResolveInfo
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

url_services = {
    "Granja": "http://granja-service:5001",
    "Ad": "http://microservicio_anuncio-demo_01_service_01-1",
    "Usuarios": "http://tarea.u4-service-users",
    "Clima": "http://clima-triste-service"
}

type_defs = load_schema_from_path("./app/schema.graphql")

query = QueryType()
mutation = MutationType()
subscription = SubscriptionType()

broadcast = Broadcast("memory://")

plants = ObjectType("Plant")
farm = ObjectType("Farm")
construction = ObjectType("Construction")
user = ObjectType("User")
ad = ObjectType("Ad")


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s')

@query.field("getPlants")
def resolve_get_plants(obj, resolve_info: GraphQLResolveInfo):
    response = requests.get(f"{url_services['Granja']}/plants")

    if response.status_code == 200:
        return response.json()
    
@query.field("getFarm")
def resolve_get_farm(obj, resolve_info: GraphQLResolveInfo, userId):
    response = requests.get(f"{url_services['Granja']}/users/{userId}")

    if response.status_code == 200:
        return response.json()
    
@query.field("getConstructions")
def resolve_get_constructions(obj, resolve_info: GraphQLResolveInfo, userId):
    response = requests.get(f"{url_services['Granja']}/users/{userId}")

    if response.status_code == 200:
        return response.json()["constructions"]
    
@query.field("getWeather")
def resolve_get_weather(obj, resolve_info: GraphQLResolveInfo, city):
    response = requests.get(f"{url_services['Clima']}/weather/{city}")

    if response.status_code == 200:
        return response.json()
    
@mutation.field("addPlant")
def resolver_create_plant(obj, resolve_info: GraphQLResolveInfo, userId, plantName, posX, posY):
    payload = dict(userId=userId, plantName=plantName, posX=posX, posY=posY)

    response = requests.post(f"{url_services['Granja']}/plants", params=payload, headers={'content-type':'application/json'})

    if response.status_code == 200:
        return payload
    
@mutation.field("addAd")
async def resolver_create_ad(obj, resolve_info: GraphQLResolveInfo, name, description):
    payload = dict(name=name, description=description)

    response = requests.post(f"{url_services['Ad']}/anuncio", json=payload)

    if response.status_code == 200:
        await broadcast.publish(channel="adAdded", message=json.dumps(payload))
        return payload
    
@subscription.source("adAdded")
async def latest_ad_subscription(_, info):
    async with broadcast.subscribe(channel="adAdded") as subscriber:
        async for ad in subscriber:
            yield json.loads(ad.message)

@subscription.field("adAdded")
def resolve_ad_added(obj, info):
    return obj

schema = make_executable_schema(type_defs, query, mutation, subscription, plants, farm, construction, user, ad)

graphql = GraphQL(
    schema=schema,
    debug=True,
    websocket_handler=GraphQLTransportWSHandler(),
)

middleware = [
    Middleware(CORSMiddleware, allow_origins=['https://frontclima.demo.inf326.nursoft.dev'], allow_methods=("GET", "POST", "OPTIONS"))
]


app = Starlette(
    debug=True,
    middleware= middleware,
    on_startup=[broadcast.connect],
    on_shutdown=[broadcast.disconnect],
)


app.mount("/graphql", graphql)
app.add_websocket_route("/graphql", graphql)