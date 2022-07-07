class Handler:
    def __init__(self, fabric):
        self.fabric = fabric

    def is_callable(self, name):
        attribute = getattr(self.fabric, name)
        return attribute

    def __call__(self, name, *args, **kwargs):
        print(f"called {name}")
        print(args)
        print(kwargs)
        if "fabric" in name:
            return getattr(self.fabric, name)(*args, **kwargs)

class Fabric:
    def get_fabric(self, id):
        print(f"getting fabric {id}")
        return f"fabric id is {id}"

class Switch:
    def __init__(self, handler):
        self.handler = handler

    def get_fabric_info(self):
        try:
            z = self.get_fabric("a")
            return z
        except:
            pass

    def __getattr__(self, name):
        print(f"getting {name} of type {type(name)}")
        attribute = self.handler.is_callable(name)
        print(f"attribute is {attribute}")
        if callable(attribute):
            def _method(*args):
                print("tried to handle unknown method " + name)
                if args:
                    print("it had arguments: " + str(args))
                y = self.handler(name, *args)
                print(f"y from handler is {y} and is {type(y)}")
                return y
            return _method
        else:
            return attribute


fabric = Fabric()
fabric.fabrics = {'a': 'a'}
print(fabric.__dict__)
handler = Handler(fabric)
switch = Switch(handler)
print(f"getting switch fabric info {switch.get_fabric_info()}")
print(switch.fabrics)


class HtmlTag:
    OPEN_TAGS = ['img', 'input']

    def __getattr__(self, name):
        def _missing(*args, **kwargs):
            if name in self.OPEN_TAGS:
                return "<{}/>".format(name)
            else:
                x = "<{0}> </{0}>".format(name)
                return x

        return _missing


html = HtmlTag()
print(html.p())
print(html.img())