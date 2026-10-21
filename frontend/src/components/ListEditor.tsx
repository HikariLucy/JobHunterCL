import { useId, useState, type KeyboardEvent } from "react";

/** Editor de listas de texto como etiquetas (cargos, habilidades, ubicaciones…). */
export function ListEditor({ label, values, onChange, placeholder, hint, validate }: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  hint?: string;
  validate?: (value: string) => string | null;
}) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const id = useId();

  const add = () => {
    const parts = draft.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
    if (!parts.length) return;
    for (const p of parts) {
      const problem = validate?.(p);
      if (problem) {
        setError(problem);
        return;
      }
    }
    const lower = new Set(values.map((v) => v.toLocaleLowerCase()));
    onChange([...values, ...parts.filter((p) => !lower.has(p.toLocaleLowerCase()))]);
    setDraft("");
    setError(null);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      add();
    } else if (e.key === "Backspace" && !draft && values.length) {
      onChange(values.slice(0, -1));
    }
  };

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="chips">
        {values.map((v) => (
          <span className="chip" key={v}>
            {v}
            <button type="button" aria-label={`Quitar ${v}`} onClick={() => onChange(values.filter((x) => x !== v))}>×</button>
          </span>
        ))}
        <input
          id={id}
          value={draft}
          placeholder={placeholder ?? "Escribe y pulsa Enter"}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKey}
          onBlur={add}
        />
      </div>
      {error ? <small className="field-error">{error}</small> : hint && <small className="muted">{hint}</small>}
    </div>
  );
}
