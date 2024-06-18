from rest_framework import permissions
from . import models


class RolePermission(permissions.BasePermission):
    """
    Check if user role has permissions for this endpoint and method.
    Note that token-related endpoints are always allowed.
    """

    def has_permission(self, request, view):
        if role_is_active(request):
            if check_has_all_endpoints(request):
                return True
            else:
                return check_has_endpoint(request)
        
        return False

def role_is_active(request):
    try:
        models.Role.objects.get(
            id=request.user.role.id, is_active=True)
    except models.Role.DoesNotExist:
        return False
    except models.Role.MultipleObjectsReturned:
        return True
    else:
        return True

def check_has_all_endpoints(request):
    try:
        models.Role.objects.get(
            id=request.user.role.id, allow_all=True)
    except models.Role.DoesNotExist:
        return False
    except models.Role.MultipleObjectsReturned:
        return True
    else:
        return True


def check_has_endpoint(request):

    if models.Role.objects.get(
            id=request.user.role.id).role_api:
        return check_has_endpoint_api(request)
    else:
        return check_has_endpoint_frontend(request)
    
def check_has_endpoint_api(request):
    role = models.Role.objects.get(
            id=request.user.role.id)
    
    for endpoint_cluster in role.endpoints_clusters.all():
        if endpoint_cluster.endpoints.filter(path = replace_path_params(request.path), method__in = [request.method, "ALL"]).exists():
            return True
        
    return False

def check_has_endpoint_frontend(request):
    role = models.Role.objects.get(
            id=request.user.role.id)
    
    for page in role.pages.all():
        for endpoint_cluster in page.endpoints_clusters.all():
            if endpoint_cluster.endpoints.filter(path = replace_path_params(request.path), method__in = [request.method, "ALL"]).exists():
                return True
        
    return False


def replace_path_params(str):
    path_parts = str.split("/")

    for i in path_parts:
        if remove_whitespaces(i).isnumeric():
            path_parts[path_parts.index(i)] = "<PATH_PARAM>"

    return "/".join(path_parts)


def remove_whitespaces(str):
    return "".join(str.split())
