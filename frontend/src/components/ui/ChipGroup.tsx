type Option<V extends string | null> = { v: V; l: string };

type SingleProps<V extends string | null> = {
  options: readonly Option<V>[];
  value: V;
  onChange: (v: V) => void;
  multi?: false;
  cols?: 2 | 3 | 4 | 6;
  variant?: 'grid' | 'segmented';
};

type MultiProps<V extends string> = {
  options: readonly Option<V>[];
  value: readonly V[];
  onChange: (v: V) => void;
  multi: true;
  cols?: 2 | 3 | 4 | 6;
  variant?: never; // multi 는 항상 grid
};

type Props<V extends string | null> = SingleProps<V> | MultiProps<Extract<V, string>>;

/**
 * 박스 칩 그룹 — 단일/복수 선택 통일.
 * - variant="grid" (default): 박스 칩 그리드. border + active 시 primary tint.
 * - variant="segmented" (단일 only): 한 박스 안 N 버튼. iOS-style segmented control.
 *   ※ 옵션 ≤4 + 단일 선택 자리 (성별/요일) 에 적합.
 */
export function ChipGroup<V extends string | null>(props: Props<V>) {
  const { options, cols = 3 } = props;
  const variant = (props as SingleProps<V>).variant ?? 'grid';

  // segmented: 단일 선택 + 한 박스 안 버튼 N개
  if (!props.multi && variant === 'segmented') {
    return (
      <div className="flex p-1 bg-muted rounded-lg border border-border">
        {options.map((opt) => {
          const active = props.value === opt.v;
          return (
            <button
              key={String(opt.v)}
              type="button"
              onClick={() => props.onChange(opt.v)}
              className={
                'flex-1 py-1.5 text-xs font-bold rounded-md transition-all ' +
                (active
                  ? 'bg-card shadow-sm text-primary'
                  : 'text-muted-foreground hover:text-foreground')
              }
            >
              {opt.l}
            </button>
          );
        })}
      </div>
    );
  }

  // grid (default): 박스 칩 그리드
  const colsClass = {
    2: 'grid-cols-2',
    3: 'grid-cols-3',
    4: 'grid-cols-4',
    6: 'grid-cols-6',
  }[cols];

  return (
    <div className={`grid ${colsClass} gap-1.5`}>
      {options.map((opt) => {
        const active = props.multi
          ? (props.value as readonly string[]).includes(opt.v as string)
          : props.value === opt.v;
        return (
          <button
            key={String(opt.v)}
            type="button"
            onClick={() =>
              props.multi ? props.onChange(opt.v as Extract<V, string>) : props.onChange(opt.v)
            }
            className={
              'h-9 px-2 rounded-lg text-[11px] font-bold border transition-all ' +
              (active
                ? 'bg-primary/5 border-primary text-primary'
                : 'bg-card border-border text-muted-foreground hover:border-primary/40 hover:bg-accent/40 hover:text-foreground')
            }
          >
            {opt.l}
          </button>
        );
      })}
    </div>
  );
}
