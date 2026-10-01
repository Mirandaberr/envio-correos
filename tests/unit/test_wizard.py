from envio_correos.gui.presenters.base import Guard, StepPresenter, Wizard, WizardContext


class Step(StepPresenter):
    def __init__(self, ctx, name, guard=None, allows_back=True):
        super().__init__(ctx)
        self.name, self.guard, self.allows_back = name, guard, allows_back
        self.events = []

    def on_enter(self):
        self.events.append("enter")

    def on_leave(self):
        self.events.append("leave")

    def can_advance(self):
        return self.guard or Guard.allow()


def make(*steps):
    return Wizard(list(steps))


def test_avanza_y_retrocede_con_ganchos():
    ctx = WizardContext()
    a, b = Step(ctx, "a"), Step(ctx, "b")
    w = make(a, b)
    assert w.next().ok and w.current is b
    assert a.events == ["enter", "leave"] and b.events == ["enter"]
    assert w.back() and w.current is a


def test_guarda_impide_avanzar_y_explica():
    ctx = WizardContext()
    w = make(Step(ctx, "a", Guard.deny("Falta el archivo")), Step(ctx, "b"))
    g = w.next()
    assert not g.ok and g.reason == "Falta el archivo" and w.index == 0


def test_no_retrocede_desde_un_paso_que_lo_prohibe():
    ctx = WizardContext()
    w = make(Step(ctx, "a"), Step(ctx, "envio", allows_back=False))
    w.next()
    assert not w.can_go_back and not w.back()


def test_ultimo_paso_no_avanza():
    ctx = WizardContext()
    w = make(Step(ctx, "a"))
    assert w.is_last and w.next().ok and w.index == 0


def test_el_contexto_persiste_entre_pasos():
    ctx = WizardContext()
    w = make(Step(ctx, "a"), Step(ctx, "b"))
    ctx.account_email = "yo@empresa.com"
    w.next()
    w.back()
    assert w.current.ctx.account_email == "yo@empresa.com"


def test_go_to():
    ctx = WizardContext()
    a, b, c = Step(ctx, "a"), Step(ctx, "b"), Step(ctx, "c")
    w = make(a, b, c)
    w.go_to(2)
    assert w.current is c and a.events[-1] == "leave"
