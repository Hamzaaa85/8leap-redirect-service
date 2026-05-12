[https://besthive.co](https://besthive.co)\
[https://aiweave.app/besthive/](https://aiweave.app/besthive/)

[https://besthive.co/who-are-we/](https://besthive.co/who-are-we/)\
[https://aiweave.app/besthive/who-are-we/](https://aiweave.app/besthive/who-are-we/)

[https://besthive.co/about-us/](https://besthive.co/about-us/)\
[https://aiweave.app/besthive/about-us/](https://aiweave.app/besthive/about-us/)



# Its not necessary to use django, we can use fastapi as well 

# middleware.py

from django.shortcuts import redirect

class DualWebRedirectMiddleware:\
def **init**(self, get\_response):\
self.get\_response = get\_response

```
def __call__(self, request):
    ua = request.META.get('HTTP_USER_AGENT', '')
    bots = ['OAI-SearchBot','ChatGPT-User','Claude','PerplexityBot']
    if any(bot in ua for bot in bots):
        target = f"https://aiwave.app{request.get_full_path()}"
        return redirect(target, permanent=True)
    return self.get_response(request)
```
