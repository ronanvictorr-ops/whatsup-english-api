import { createFileRoute } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Play,
  Timer,
  Brain,
  CalendarCheck,
  TrendingUp,
  Target,
  Bot,
  Check,
  Star,
  Instagram,
  Youtube,
  Mail,
  Phone,
  MessageCircle,
  Wifi,
  Globe,
  Bell,
  User,
} from "lucide-react";
import wingoAsset from "@/assets/wingo.png.asset.json";
import wingoCellAsset from "@/assets/wingo-cell.png.asset.json";
import wingoMeetAsset from "@/assets/wingo-meet-v3.png.asset.json";
const wingoHero = wingoCellAsset.url;
const wingoThumbs = wingoAsset.url;
import logoAsset from "@/assets/whatsup-logo-header-v3.png.asset.json";
import logoLightAsset from "@/assets/whatsup-logo-footer-v2.png.asset.json";
import flagUsa from "@/assets/flag-usa.png.asset.json";
import flagUk from "@/assets/flag-uk.png.asset.json";
import flagCan from "@/assets/flag-can.png.asset.json";

function WhatsAppIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12.05 21.785h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.999-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.886 9.884zm8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z" />
    </svg>
  );
}

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "WhatsUp English — Aprenda inglês pelo WhatsApp com o Wingo" },
      {
        name: "description",
        content:
          "Aulas rápidas, prática diária e correções inteligentes direto no WhatsApp. Evolua no inglês de forma simples, leve e no seu ritmo com o Wingo.",
      },
      { property: "og:title", content: "WhatsUp English — Aprenda inglês pelo WhatsApp" },
      {
        property: "og:description",
        content: "Aulas rápidas e corretor inteligente direto no WhatsApp com o Wingo.",
      },
      { property: "og:type", content: "website" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <div className="min-h-screen bg-background font-sans text-[color:var(--brand-ink)]">
      <Nav />
      <Hero />
      <HowItWorks />
      <WhyWingo />
      <MeetWingo />
      <Plans />
      <Testimonials />
      <FAQ />
      <FinalCTA />
      <Footer />
    </div>
  );
}

/* ---------- NAV ---------- */
function Logo() {
  return (
    <a href="#top" className="flex shrink-0 items-center" aria-label="WhatsUp English">
      <img src={logoAsset.url} alt="WhatsUp English" className="-my-2 h-10 w-auto md:h-14" />
    </a>
  );
}

function Nav() {
  const links = [
    { href: "#top", label: "Início" },
    { href: "#como-funciona", label: "Como funciona" },
    { href: "#beneficios", label: "Benefícios" },
    { href: "#planos", label: "Planos" },
    { href: "#faq", label: "FAQ" },
  ];
  return (
    <header
      id="top"
      className="sticky top-0 z-40 border-b border-border/60 bg-background/85 backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-2 sm:gap-6 sm:px-6">
        <Logo />
        <nav className="hidden items-center gap-12 lg:flex">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-base font-semibold text-[color:var(--brand-ink)]/80 transition-colors hover:text-[color:var(--brand-blue)]"
            >
              {l.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2 sm:gap-3">
          <Button variant="hero" size="lg" className="hidden rounded-full sm:inline-flex">
            <WhatsAppIcon className="h-5 w-5" />
            Começar agora
          </Button>
          <a
            href="/promocoes"
            aria-label="Promoções e avisos"
            className="relative rounded-full p-2 text-[color:var(--brand-ink)]/70 transition-colors hover:bg-white/60 hover:text-[color:var(--brand-ink)]"
          >
            <Bell className="h-6 w-6" strokeWidth={2} />
            <span className="absolute -top-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white shadow-sm">
              3
            </span>
          </a>
          <a
            href="/auth"
            className="grid h-10 w-10 place-items-center rounded-full bg-gray-200 text-gray-400 transition-colors hover:bg-gray-300"
            aria-label="Entrar"
          >
            <User className="h-5 w-5" />
          </a>
        </div>
      </div>
    </header>
  );
}

/* ---------- HERO ---------- */
function Hero() {
  return (
    <section className="relative overflow-hidden [background:var(--gradient-hero)]">
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 py-16 lg:grid-cols-2 lg:py-24">
        <div>
          <h1 className="font-display text-5xl leading-[1.05] font-extrabold tracking-tight sm:text-6xl">
            Aprenda inglês <br />
            pelo <span className="text-[color:var(--brand-green-deep)]">WhatsApp</span> <br />
            com a ajuda do <span className="text-[color:var(--brand-blue)]">WINGO</span>
          </h1>
          <p className="mt-6 max-w-lg text-lg text-[color:var(--brand-ink)]/70">
            Aulas rápidas, prática diária e correções inteligentes para você evoluir no inglês de
            forma simples, leve e no seu ritmo.
          </p>
          <div className="relative z-30 mt-8 flex flex-row flex-nowrap items-center gap-3 sm:gap-4">
            <Button
              variant="whatsapp"
              size="lg"
              className="flex-1 sm:flex-none sm:size-xl whitespace-nowrap"
            >
              <WhatsAppIcon className="h-5 w-5 sm:h-6 sm:w-6" />
              Começar agora
            </Button>
            <Button
              variant="soft"
              size="lg"
              className="flex-1 sm:flex-none rounded-full whitespace-nowrap"
            >
              <Play className="h-4 w-4 fill-current" />
              Ver como funciona
            </Button>
          </div>
        </div>

        <div className="relative flex items-center justify-center lg:-mr-16 xl:-mr-28">
          <div className="absolute inset-0 rounded-full bg-white/60 blur-2xl" aria-hidden />
          <div
            className="absolute left-1/2 top-1/2 h-[380px] w-[380px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[color:var(--brand-blue)]/15"
            aria-hidden
          />
          <img
            src={wingoHero}
            alt="Wingo, o professor virtual de inglês"
            width={1920}
            height={1080}
            className="relative z-10 w-full max-w-none scale-[1.85] lg:scale-[2.4] xl:scale-[2.75] drop-shadow-2xl"
          />
        </div>
      </div>
    </section>
  );
}

function FloatBadge({
  className = "",
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`absolute z-20 grid h-[72px] w-[72px] place-items-center rounded-full shadow-[var(--shadow-card)] ${className}`}
    >
      {children}
    </div>
  );
}

function RingBadge({
  top,
  left,
  className = "",
  children,
}: {
  top: string;
  left: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{ top, left, transform: "translate(-50%, -50%)" }}
      className={`absolute z-20 grid h-[72px] w-[72px] place-items-center rounded-full shadow-[var(--shadow-card)] ${className}`}
    >
      {children}
    </div>
  );
}

/* ---------- HOW IT WORKS ---------- */
function HowItWorks() {
  const steps = [
    {
      n: "01",
      icon: <WhatsAppIcon className="h-9 w-9 text-white" />,
      iconBg: "var(--brand-green)",
      title: "Você chama no WhatsApp",
      desc: "Comece sua aula direto pelo aplicativo que você já usa todos os dias.",
    },
    {
      n: "02",
      icon: <Bot className="h-8 w-8 text-white" />,
      iconBg: "var(--brand-blue)",
      title: "O Wingo te guia",
      desc: "Nosso professor virtual ensina, corrige e acompanha seu progresso.",
    },
    {
      n: "03",
      icon: <Target className="h-8 w-8 text-white" />,
      iconBg: "var(--brand-yellow)",
      title: "Você evolui diariamente",
      desc: "Aulas curtas, exercícios práticos e revisão constante.",
    },
  ];
  return (
    <section id="como-funciona" className="py-20">
      <div className="mx-auto max-w-7xl px-6">
        <h2 className="text-center font-display text-3xl font-extrabold sm:text-4xl">
          Como o <span className="text-[color:var(--brand-green-deep)]">Wingo</span> funciona?
        </h2>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {steps.map((s) => (
            <article
              key={s.n}
              className="rounded-3xl border border-border bg-card p-8 shadow-[var(--shadow-card)] transition-transform hover:-translate-y-1"
            >
              <div className="flex items-start gap-5">
                <div
                  className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl shadow-md"
                  style={{ background: s.iconBg }}
                >
                  {s.icon}
                </div>
                <div>
                  <div className="font-display text-2xl font-extrabold text-[color:var(--brand-green-deep)]">
                    {s.n}
                  </div>
                  <h3 className="mt-1 font-display text-lg font-bold">{s.title}</h3>
                </div>
              </div>
              <p className="mt-5 text-[color:var(--brand-ink)]/70">{s.desc}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- WHY WINGO ---------- */
function WhyWingo() {
  const features = [
    {
      icon: Timer,
      color: "var(--brand-blue)",
      title: "Aulas rápidas",
      desc: "Estude mesmo com pouco tempo.",
    },
    {
      icon: Brain,
      color: "var(--brand-green-deep)",
      title: "Correção inteligente",
      desc: "Receba feedback nas suas respostas.",
    },
    {
      icon: CalendarCheck,
      color: "var(--brand-yellow)",
      title: "Prática diária",
      desc: "Crie constância no inglês.",
    },
    {
      icon: TrendingUp,
      color: "oklch(0.55 0.2 300)",
      title: "Do básico ao avançado",
      desc: "Conteúdo organizado aula por aula.",
    },
  ];
  return (
    <section id="beneficios" className="py-16">
      <div className="mx-auto grid max-w-7xl gap-10 px-6 lg:grid-cols-[1fr_2fr] lg:items-center">
        <h2 className="font-display text-3xl font-extrabold leading-tight sm:text-4xl lg:self-center">
          Por que aprender com <br />o <span className="text-[color:var(--brand-blue)]">WINGO</span>
          ?
        </h2>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((f) => (
            <div key={f.title} className="text-center">
              <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-[color:var(--brand-bg-soft)]">
                <f.icon className="h-8 w-8" style={{ color: f.color }} strokeWidth={2.25} />
              </div>
              <h3 className="mt-4 font-display font-bold">{f.title}</h3>
              <p className="mt-1 text-sm text-[color:var(--brand-ink)]/70">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- MEET WINGO BANNER ---------- */
function MeetWingo() {
  return (
    <section className="px-6 py-16">
      <div className="relative mx-auto max-w-7xl overflow-visible rounded-[2.5rem] px-8 py-3 sm:px-12 sm:py-4 [background:var(--gradient-blue)]">
        <div className="grid items-center gap-6 md:grid-cols-[minmax(220px,300px)_1fr_auto]">
          <div className="relative mx-auto flex h-36 w-full items-end justify-center sm:h-44 md:h-52 lg:h-56">
            <img
              src={wingoMeetAsset.url}
              alt="Wingo cumprimentando com balões de chat"
              loading="lazy"
              width={1920}
              height={1040}
              className="absolute bottom-[-20%] left-1/2 h-[180%] w-auto max-w-none -translate-x-1/2 object-contain drop-shadow-2xl sm:h-[190%] md:h-[200%] lg:h-[210%]"
            />
          </div>
          <div className="text-white">
            <h2 className="font-display text-3xl font-extrabold sm:text-4xl">
              Conheça o <span className="text-[color:var(--brand-green)]">WINGO</span>
            </h2>
            <p className="mt-4 max-w-xl text-white/90">
              Oi! Eu sou o Wingo, seu professor virtual de inglês. Vou te ajudar a aprender novas
              palavras, montar frases, praticar conversação e ganhar confiança no inglês.
            </p>
          </div>
          <Button variant="whatsapp" size="xl" className="justify-self-start md:justify-self-end">
            <WhatsAppIcon className="h-6 w-6" />
            Falar com o Wingo
          </Button>
        </div>
      </div>
    </section>
  );
}

/* ---------- PLANS ---------- */
type Plan = {
  name: string;
  tagline: string;
  price: string;
  features: string[];
  highlighted?: boolean;
  cta: string;
  ctaVariant: "whatsapp" | "hero" | "default";
  accent: string;
};

function Plans() {
  const plans: Plan[] = [
    {
      name: "Básico",
      tagline: "Para quem quer começar do zero.",
      price: "29,90",
      features: [
        "Aulas introdutórias",
        "Vocabulário essencial",
        "Exercícios básicos",
        "Suporte por WhatsApp",
      ],
      cta: "Começar",
      ctaVariant: "whatsapp",
      accent: "var(--brand-green-deep)",
    },
    {
      name: "Plus",
      tagline: "Para quem quer evoluir com prática diária.",
      price: "39,90",
      features: [
        "Aulas completas",
        "Correções inteligentes",
        "Exercícios práticos",
        "Acompanhamento de progresso",
        "Suporte prioritário",
      ],
      highlighted: true,
      cta: "Quero esse",
      ctaVariant: "hero",
      accent: "var(--brand-blue)",
    },
    {
      name: "Premium",
      tagline: "Para quem quer acompanhamento mais completo.",
      price: "59,90",
      features: [
        "Tudo do plano Plus",
        "Conversação guiada",
        "Revisões personalizadas",
        "Suporte avançado",
      ],
      cta: "Entrar no Premium",
      ctaVariant: "default",
      accent: "oklch(0.55 0.2 300)",
    },
  ];

  return (
    <section id="planos" className="py-20">
      <div className="mx-auto max-w-7xl px-6">
        <h2 className="text-center font-display text-3xl font-extrabold sm:text-4xl">
          Escolha seu plano
        </h2>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {plans.map((p) => (
            <div
              key={p.name}
              className={`relative rounded-3xl border bg-card p-8 shadow-[var(--shadow-card)] transition-transform hover:-translate-y-1 ${
                p.highlighted
                  ? "border-[color:var(--brand-blue)]/40 ring-2 ring-[color:var(--brand-blue)]/30"
                  : "border-border"
              }`}
            >
              {p.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-[color:var(--brand-blue)] px-4 py-1 text-xs font-bold text-white shadow">
                  Mais escolhido
                </div>
              )}
              <h3
                className="text-center font-display text-2xl font-extrabold"
                style={{ color: p.accent }}
              >
                {p.name}
              </h3>
              <p className="mt-2 text-center text-sm text-[color:var(--brand-ink)]/70">
                {p.tagline}
              </p>
              <div className="mt-6 text-center">
                <span className="text-sm font-semibold align-top">R$</span>{" "}
                <span className="font-display text-5xl font-extrabold" style={{ color: p.accent }}>
                  {p.price}
                </span>
                <span className="text-sm text-[color:var(--brand-ink)]/60">/mês</span>
              </div>
              <ul className="mt-6 space-y-3">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-sm">
                    <Check
                      className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--brand-green-deep)]"
                      strokeWidth={3}
                    />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Button
                variant={p.ctaVariant === "default" ? "default" : p.ctaVariant}
                size="lg"
                className={`mt-8 w-full rounded-full ${
                  p.ctaVariant === "default"
                    ? "bg-[oklch(0.55_0.2_300)] text-white hover:bg-[oklch(0.5_0.2_300)]"
                    : ""
                }`}
              >
                {p.cta}
              </Button>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- TESTIMONIALS ---------- */
function Testimonials() {
  const items = [
    {
      name: "Pedro Santos",
      img: "https://i.pravatar.cc/120?img=12",
      text: "Comecei do zero e já consigo formar minhas primeiras frases. O Wingo é demais!",
    },
    {
      name: "Juliana Lima",
      img: "https://i.pravatar.cc/120?img=47",
      text: "O Wingo explica de um jeito simples e fácil de entender. Estou adorando!",
    },
    {
      name: "Carlos Almeida",
      img: "https://i.pravatar.cc/120?img=33",
      text: "Estudo no caminho do trabalho, todo dia. Nunca foi tão prático aprender inglês.",
    },
  ];
  return (
    <section className="py-16">
      <div className="mx-auto max-w-5xl px-6">
        <h2 className="text-center font-display text-3xl font-extrabold sm:text-4xl">
          O que nossos alunos dizem
        </h2>
        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {items.slice(0, 2).map((t) => (
            <figure
              key={t.name}
              className="flex items-start gap-4 rounded-3xl border border-border bg-card p-6 shadow-[var(--shadow-card)]"
            >
              <img
                src={t.img}
                alt={t.name}
                loading="lazy"
                className="h-14 w-14 shrink-0 rounded-full object-cover"
              />
              <div>
                <blockquote className="text-[color:var(--brand-ink)]/85">"{t.text}"</blockquote>
                <figcaption className="mt-3 font-semibold text-[color:var(--brand-ink)]">
                  — {t.name}
                </figcaption>
              </div>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------- FAQ ---------- */
function FAQ() {
  const faqs = [
    {
      q: "Preciso instalar outro aplicativo?",
      a: "Não. Tudo acontece pelo WhatsApp que você já usa.",
    },
    {
      q: "Serve para iniciantes?",
      a: "Sim. O curso começa do básico e você aprende no seu ritmo.",
    },
    {
      q: "Posso estudar em qualquer horário?",
      a: "Sim. Você estuda quando puder, como e onde quiser.",
    },
    {
      q: "Tem correção?",
      a: "Sim. A IA corrige suas respostas e te orienta para você melhorar.",
    },
  ];
  return (
    <section id="faq" className="py-20">
      <div className="mx-auto max-w-4xl px-6">
        <h2 className="text-center font-display text-3xl font-extrabold sm:text-4xl">
          Perguntas frequentes
        </h2>
        <Accordion type="single" collapsible className="mt-10 space-y-3">
          {faqs.map((f, i) => (
            <AccordionItem
              key={i}
              value={`item-${i}`}
              className="rounded-2xl border border-border bg-card px-5 shadow-[var(--shadow-card)]"
            >
              <AccordionTrigger className="text-left font-semibold hover:no-underline">
                <span className="flex items-center gap-3">
                  <WhatsAppIcon className="h-4 w-4 text-[color:var(--brand-green-deep)]" />
                  {f.q}
                </span>
              </AccordionTrigger>
              <AccordionContent className="text-[color:var(--brand-ink)]/75">
                {f.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}

/* ---------- FINAL CTA ---------- */
function FinalCTA() {
  return (
    <section className="px-6 pb-10">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 rounded-[2rem] px-8 py-10 text-white shadow-[var(--shadow-cta)] md:flex-row [background:var(--gradient-cta)]">
        <div>
          <h2 className="font-display text-2xl font-extrabold sm:text-3xl">
            Comece hoje sua jornada no inglês
          </h2>
          <p className="mt-2 text-white/90">
            Aprenda de forma prática, moderna e divertida com o WhatsUp English.
          </p>
        </div>
        <Button
          size="xl"
          className="rounded-full bg-white text-[color:var(--brand-green-deep)] hover:bg-white/90"
        >
          <WhatsAppIcon className="h-6 w-6" />
          Começar agora pelo WhatsApp
        </Button>
      </div>
    </section>
  );
}

/* ---------- FOOTER ---------- */
function Footer() {
  return (
    <footer className="bg-[color:var(--brand-ink)] text-white">
      <div className="mx-auto grid max-w-7xl gap-6 px-6 py-4 md:grid-cols-4">
        <div>
          <a href="#top" className="flex items-center" aria-label="WhatsUp English">
            <img src={logoLightAsset.url} alt="WhatsUp English" className="h-24 w-auto" />
          </a>
          <p className="mt-2 text-sm text-white/60">No seu ritmo. Pelo WhatsApp, com IA.</p>
          <div className="mt-3 flex gap-3">
            <SocialIcon>
              <Instagram className="h-4 w-4" />
            </SocialIcon>
            <SocialIcon>
              <WhatsAppIcon className="h-6 w-6" />
            </SocialIcon>
            <SocialIcon>
              <Youtube className="h-4 w-4" />
            </SocialIcon>
          </div>
        </div>
        <FooterCol
          title="Navegação"
          items={["Início", "Como funciona", "Benefícios", "Planos", "FAQ"]}
        />
        <FooterCol
          title="Suporte"
          items={[
            "Falar com o Wingo",
            "Central de ajuda",
            "Política de Privacidade",
            "Termos de Uso",
          ]}
        />
        <div>
          <h4 className="font-display font-bold">Contato</h4>
          <ul className="mt-4 space-y-3 text-sm text-white/70">
            <li className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              contato@whatsupenglish.com.br
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10 py-2 text-center text-xs text-white/50">
        © 2026 WhatsUp English. Todos os direitos reservados.
      </div>
    </footer>
  );
}

function SocialIcon({ children }: { children: React.ReactNode }) {
  return (
    <a
      href="#"
      className="grid h-9 w-9 place-items-center rounded-lg bg-[color:var(--brand-green-deep)] text-white transition-transform hover:scale-110"
    >
      {children}
    </a>
  );
}

function FooterCol({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="font-display font-bold">{title}</h4>
      <ul className="mt-4 space-y-2 text-sm text-white/70">
        {items.map((i) => (
          <li key={i}>
            <a href="#" className="hover:text-white">
              {i}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
