import { createFileRoute, Link } from "@tanstack/react-router";
import { Bell, ArrowLeft } from "lucide-react";

export const Route = createFileRoute("/promocoes")({
  component: PromocoesPage,
  head: () => ({
    meta: [
      { title: "Promoções e Avisos | WhatsUp English" },
      {
        name: "description",
        content: "Confira as últimas promoções, novidades e avisos da WhatsUp English.",
      },
    ],
  }),
});

type Item = {
  id: string;
  tag: "Promoção" | "Aviso" | "Novidade";
  title: string;
  description: string;
  date: string;
};

const items: Item[] = [
  {
    id: "1",
    tag: "Promoção",
    title: "30% OFF no plano anual",
    description:
      "Aproveite desconto exclusivo na assinatura anual de qualquer plano até o fim do mês.",
    date: "Hoje",
  },
  {
    id: "2",
    tag: "Novidade",
    title: "Novas aulas de conversação ao vivo",
    description:
      "Agora você pode participar de sessões semanais com professores nativos direto pelo WhatsApp.",
    date: "Ontem",
  },
  {
    id: "3",
    tag: "Aviso",
    title: "Manutenção programada",
    description: "Nosso sistema estará em manutenção no domingo das 02h às 04h.",
    date: "Há 2 dias",
  },
];

const tagStyles: Record<Item["tag"], string> = {
  Promoção: "bg-[color:var(--brand-blue)]/10 text-[color:var(--brand-blue)]",
  Aviso: "bg-red-50 text-red-600",
  Novidade: "bg-emerald-50 text-emerald-600",
};

function PromocoesPage() {
  return (
    <main className="min-h-screen bg-background">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-semibold text-[color:var(--brand-ink)]/70 transition-colors hover:text-[color:var(--brand-blue)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Voltar ao início
        </Link>

        <header className="mt-6 flex items-center gap-4">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[color:var(--brand-blue)]/10 text-[color:var(--brand-blue)]">
            <Bell className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-display text-3xl font-black text-[color:var(--brand-ink)]">
              Promoções e Avisos
            </h1>
            <p className="text-sm text-[color:var(--brand-ink)]/60">
              Fique por dentro das novidades da WhatsUp English.
            </p>
          </div>
        </header>

        <ul className="mt-10 space-y-4">
          {items.map((item) => (
            <li
              key={item.id}
              className="rounded-2xl border border-border bg-card p-6 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="flex items-center justify-between gap-4">
                <span className={`rounded-full px-3 py-1 text-xs font-bold ${tagStyles[item.tag]}`}>
                  {item.tag}
                </span>
                <span className="text-xs text-[color:var(--brand-ink)]/50">{item.date}</span>
              </div>
              <h2 className="mt-3 font-display text-lg font-bold text-[color:var(--brand-ink)]">
                {item.title}
              </h2>
              <p className="mt-1 text-sm text-[color:var(--brand-ink)]/70">{item.description}</p>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
