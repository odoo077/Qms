from django.shortcuts import render

# Create your views here.


def tailwind_test(request):
    return render(request, 'employees/tailwind_test.html')


def home(request):
    return render(request, 'employees/home.html')


def uploaddata(request):
    return render(request, 'employees/uploaddata.html')