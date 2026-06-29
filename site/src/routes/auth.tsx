import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  ArrowRight,
  Mail,
  Lock,
  Eye,
  EyeOff,
  User as UserIcon,
  Building2,
  ShieldCheck,
  Headphones,
  Users,
  LineChart,
  GraduationCap,
} from "lucide-react";
import wingoCellAsset from "@/assets/wingo-teacher.png.asset.json";
import logoAsset from "@/assets/whatsup-logo-header-v3.png.asset.json";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "Login — WhatsUp English" },
      {
        name: "description",
        content:
          "Área exclusiva para professores e escolas parceiras da WhatsUp English. Acesse a plataforma e gerencie suas turmas com o WINGO.",
      },
      { property: "og:title", content: "Login — WhatsUp English" },
      {
        property: "og:description",
        content:
          "Acesse a plataforma WhatsUp English: gestão de alunos, relatórios inteligentes e aulas com integração ao WhatsApp.",
      },
    ],
  }),
  component: AuthPage,
});

function WhatsAppIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.095 3.2 5.076 4.487.709.306 1.263.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347zM12.05 21.785h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.999-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.886 9.884zm8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z" />
    </svg>
  );
}

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className={className}>
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571.001-.001.002-.001.003-.002l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  );
}

function AuthPage() {
  const [role, setRole] = useState<"professor" | "escola">("professor");
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="min-h-screen w-full bg-[#070b12] text-white">
      <div className="grid min-h-screen w-full lg:grid-cols-[minmax(0,520px)_1fr]">
        {/* LEFT — Login card */}
        <aside className="flex items-center justify-center bg-sky-100 px-6 py-10 text-[color:var(--brand-ink)] sm:px-10 lg:px-14">
          <div className="w-full max-w-md">
            <Link to="/" className="flex justify-center" aria-label="WhatsUp English">
              <img src={logoAsset.url} alt="WhatsUp English" className="h-24 w-auto sm:h-28" />
            </Link>

            <h1 className="mt-8 font-display text-4xl font-extrabold tracking-tight sm:text-5xl">
              Bem-vindo(a)!
            </h1>
            <p className="mt-3 text-base text-[color:var(--brand-ink)]/70">
              Área exclusiva para{" "}
              <span className="font-bold text-[color:var(--brand-green-deep)]">professores</span> e{" "}
              <span className="font-bold text-[color:var(--brand-green-deep)]">escolas</span>{" "}
              parceiras.
            </p>

            {/* Role toggle */}
            <div className="mt-7 grid grid-cols-2 gap-3 rounded-2xl bg-gray-100 p-1.5">
              <button
                type="button"
                onClick={() => setRole("professor")}
                className={`flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition ${
                  role === "professor"
                    ? "bg-[color:var(--brand-green-deep)] text-white shadow-sm"
                    : "text-[color:var(--brand-ink)]/70 hover:text-[color:var(--brand-ink)]"
                }`}
              >
                <UserIcon className="h-4 w-4" />
                Professor
              </button>
              <button
                type="button"
                onClick={() => setRole("escola")}
                className={`flex items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold transition ${
                  role === "escola"
                    ? "bg-[color:var(--brand-green-deep)] text-white shadow-sm"
                    : "text-[color:var(--brand-ink)]/70 hover:text-[color:var(--brand-ink)]"
                }`}
              >
                <Building2 className="h-4 w-4" />
                Escola Parceira
              </button>
            </div>

            <form className="mt-6 space-y-4" onSubmit={(e) => e.preventDefault()}>
              <div>
                <label htmlFor="email" className="text-sm font-semibold">
                  E-mail
                </label>
                <div className="relative mt-2">
                  <Mail className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-[color:var(--brand-ink)]/40" />
                  <input
                    id="email"
                    type="email"
                    placeholder="Digite seu e-mail"
                    className="w-full rounded-xl border border-gray-200 bg-white py-3 pr-4 pl-11 text-sm placeholder:text-[color:var(--brand-ink)]/40 focus:border-[color:var(--brand-green-deep)] focus:ring-2 focus:ring-[color:var(--brand-green-deep)]/30 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="password" className="text-sm font-semibold">
                  Senha
                </label>
                <div className="relative mt-2">
                  <Lock className="pointer-events-none absolute top-1/2 left-4 h-4 w-4 -translate-y-1/2 text-[color:var(--brand-ink)]/40" />
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Digite sua senha"
                    className="w-full rounded-xl border border-gray-200 bg-white py-3 pr-12 pl-11 text-sm placeholder:text-[color:var(--brand-ink)]/40 focus:border-[color:var(--brand-green-deep)] focus:ring-2 focus:ring-[color:var(--brand-green-deep)]/30 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                    className="absolute top-1/2 right-3 -translate-y-1/2 rounded-md p-1.5 text-[color:var(--brand-ink)]/50 hover:bg-gray-100"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <label className="flex items-center gap-2 text-sm text-[color:var(--brand-ink)]/80">
                  <input
                    type="checkbox"
                    defaultChecked
                    className="h-4 w-4 accent-[color:var(--brand-green-deep)]"
                  />
                  Lembrar de mim
                </label>
                <a
                  href="#"
                  className="text-sm font-semibold text-[color:var(--brand-blue)] hover:underline"
                >
                  Esqueci minha senha
                </a>
              </div>

              <Button
                type="submit"
                variant="whatsapp"
                size="xl"
                className="mt-2 w-full justify-center"
              >
                <WhatsAppIcon className="h-6 w-6" />
                Entrar na plataforma
                <ArrowRight className="h-5 w-5" />
              </Button>

              <div className="flex items-center gap-3 py-1 text-xs text-[color:var(--brand-ink)]/50">
                <span className="h-px flex-1 bg-gray-200" />
                ou
                <span className="h-px flex-1 bg-gray-200" />
              </div>

              <button
                type="button"
                className="flex w-full items-center justify-center gap-3 rounded-xl border border-gray-200 bg-white py-3.5 text-sm font-semibold text-[color:var(--brand-ink)] transition hover:bg-gray-50"
              >
                <GoogleIcon className="h-5 w-5" />
                Entrar com Google
              </button>
            </form>

            <p className="mt-7 text-center text-sm text-[color:var(--brand-ink)]/70">
              Ainda não tem acesso?{" "}
              <a href="#" className="font-semibold text-[color:var(--brand-blue)] hover:underline">
                Fale com nosso time
              </a>
            </p>
          </div>
        </aside>

        {/* RIGHT — Hero pitch */}
        <section className="relative hidden overflow-hidden bg-[radial-gradient(ellipse_at_80%_50%,rgba(16,185,129,0.18),transparent_60%),linear-gradient(180deg,#070b12_0%,#0a1320_100%)] lg:block">
          {/* Top chips */}
          <div className="relative z-10 flex items-start justify-between gap-4 px-10 pt-10">
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur-sm">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-[color:var(--brand-green-deep)]/20 text-[color:var(--brand-green)]">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <div className="leading-tight">
                <p className="text-sm font-semibold">Ambiente seguro</p>
                <p className="text-xs text-white/60">Seus dados protegidos</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur-sm">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-[color:var(--brand-green-deep)]/20 text-[color:var(--brand-green)]">
                <Headphones className="h-5 w-5" />
              </span>
              <div className="leading-tight">
                <p className="text-sm font-semibold">Suporte Exclusivo</p>
                <p className="text-xs text-white/60">Professores e Escolas</p>
              </div>
            </div>
          </div>

          <div className="relative z-10 grid grid-cols-[1.1fr_1fr] items-center gap-6 px-10 pt-10">
            <div>
              <h2 className="font-display text-5xl leading-[1.05] font-extrabold tracking-tight">
                Gerencie, ensine e transforme vidas com o{" "}
                <span className="text-[color:var(--brand-green)]">WINGO.</span>
              </h2>
              <div className="mt-4 h-1 w-16 rounded-full bg-[color:var(--brand-green)]" />
              <p className="mt-6 max-w-md text-base text-white/75">
                Acompanhe seus alunos, crie aulas, acesse relatórios e{" "}
                <span className="font-semibold text-[color:var(--brand-green)]">potencialize</span>{" "}
                os <span className="font-semibold text-[color:var(--brand-green)]">resultados</span>{" "}
                da sua escola.
              </p>
            </div>

            <div className="relative flex items-end justify-center">
              <img
                src={wingoCellAsset.url}
                alt="Wingo com tablet"
                className="h-[560px] w-auto object-contain drop-shadow-[0_30px_40px_rgba(16,185,129,0.25)]"
              />
            </div>
          </div>

          {/* Features grid */}
          <div className="relative z-10 mt-4 grid grid-cols-4 gap-4 px-10">
            {[
              {
                icon: Users,
                title: "Gestão completa de alunos",
                desc: "Acompanhe o progresso e desempenho em tempo real.",
              },
              {
                icon: LineChart,
                title: "Relatórios inteligentes",
                desc: "Dados que ajudam a tomar decisões e gerar resultados.",
              },
              {
                icon: GraduationCap,
                title: "Aulas e conteúdos exclusivos",
                desc: "Materiais alinhados ao método WhatsUp English.",
              },
              {
                icon: WhatsAppIcon,
                title: "Integração com WhatsApp",
                desc: "Ensino prático, moderno e sempre acessível.",
              },
            ].map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-sm"
              >
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-[color:var(--brand-green-deep)]/20 text-[color:var(--brand-green)]">
                  <f.icon className="h-5 w-5" />
                </span>
                <h3 className="mt-3 font-display text-base font-bold leading-tight">{f.title}</h3>
                <p className="mt-2 text-xs text-white/60">{f.desc}</p>
              </div>
            ))}
          </div>

          {/* Bottom strip */}
          <div className="relative z-10 mx-10 mt-6 mb-10 flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-4 backdrop-blur-sm">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-[color:var(--brand-green-deep)]/20 text-[color:var(--brand-green)]">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <p className="text-sm text-white/80">
                Plataforma desenvolvida para quem ensina com paixão
                <br />e transforma o futuro através do inglês.
              </p>
            </div>
            <a
              href="#"
              aria-label="Falar no WhatsApp"
              className="grid h-12 w-12 place-items-center rounded-full bg-[color:var(--brand-green-deep)]/20 text-[color:var(--brand-green)] ring-1 ring-[color:var(--brand-green)]/30 transition hover:bg-[color:var(--brand-green-deep)]/30"
            >
              <WhatsAppIcon className="h-6 w-6" />
            </a>
          </div>
        </section>
      </div>
    </div>
  );
}
