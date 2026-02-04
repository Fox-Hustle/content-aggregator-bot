#!/bin/bash

# Останавливаемся при ошибках
set -euo pipefail

# ============================================
# Ранняя инициализация для cleanup
# ============================================
LIST_FILE=""
FILTERED_LIST=""

cleanup() {
    [[ -n "$LIST_FILE" ]] && rm -f "$LIST_FILE"
    [[ -n "$FILTERED_LIST" ]] && rm -f "$FILTERED_LIST"
}
trap cleanup EXIT

# ============================================
# Проверка зависимостей
# ============================================
if ! command -v perl &>/dev/null; then
    echo "Ошибка: требуется perl" >&2
    exit 1
fi

# ============================================
# Значения по умолчанию
# ============================================
TARGET_DIR="."
OUTPUT_FILE="project_docs.md"
IGNORE_FILE=""
# Список расширений, которые мы хотим видеть в документации
EXTENSIONS="py|sh|js|ts|jsx|tsx|go|rs|java|cpp|c|h|hpp|rb|php|swift|kt|scala|vue|svelte|css|scss|html|sql|yaml|yml|toml|json|md|dockerfile|makefile|tf|conf|ini"

# ============================================
# Функция: Справка
# ============================================
usage() {
    echo "Использование: $0 -t <папка> -o <файл> [-i <файл_игнора>]"
    echo ""
    echo "Опции:"
    echo "  -t   Путь к папке проекта (по умолчанию: текущая)"
    echo "  -o   Путь к выходному файлу (по умолчанию: project_docs.md)"
    echo "  -i   Путь к файлу с паттернами для игнорирования (как grep regex)"
    echo "  -h   Показать эту справку"
    exit 1
}

# ============================================
# Разбор аргументов
# ============================================
while getopts "t:o:i:h" opt; do
    case $opt in
        t) TARGET_DIR="$OPTARG" ;;
        o) OUTPUT_FILE="$OPTARG" ;;
        i) IGNORE_FILE="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

# Проверки
if [[ ! -d "$TARGET_DIR" ]]; then
    echo "Ошибка: Папка '$TARGET_DIR' не найдена." >&2
    exit 1
fi

# ============================================
# Вспомогательные функции
# ============================================

# Проверка на бинарность (исключаем картинки и скомпилированные файлы)
is_text_file() {
    grep -Iq . "$1" 2>/dev/null || [[ ! -s "$1" ]]
}

# Определение языка для Markdown
get_language_tag() {
    local ext="${1##*.}"
    ext="${ext,,}" # в нижний регистр

    case "$ext" in
        py) echo "python" ;;
        js|jsx) echo "javascript" ;;
        ts|tsx) echo "typescript" ;;
        sh) echo "bash" ;;
        rs) echo "rust" ;;
        md) echo "markdown" ;;
        yml) echo "yaml" ;;
        *)
           local filename
           filename=$(basename "$1" | tr '[:upper:]' '[:lower:]')
           if [[ "$filename" == "dockerfile" ]]; then echo "dockerfile";
           elif [[ "$filename" == "makefile" ]]; then echo "makefile";
           else echo "$ext"; fi
           ;;
    esac
}

# Генератор дерева (Perl)
generate_tree_view() {
    perl -e '
    use strict; use warnings;
    my %tree;
    while (<>) {
        chomp;
        my @parts = split /\//;
        my $leaf = pop @parts;
        my $node = \%tree;
        for my $part (@parts) { $node = $node->{$part} //= {}; }
        $node->{$leaf} = undef;
    }
    sub print_tree {
        my ($node, $prefix) = @_;
        my @keys = sort keys %$node;
        for my $i (0 .. $#keys) {
            my $key = $keys[$i];
            my $last = ($i == $#keys);
            print $prefix . ($last ? "└── " : "├── ") . $key . "\n";
            if (defined $node->{$key}) { print_tree($node->{$key}, $prefix . ($last ? "    " : "│   ")); }
        }
    }
    print ".\n";
    print_tree(\%tree, "");
    '
}

# ============================================
# Основной процесс
# ============================================

echo "--- Настройки ---"
echo "Цель:  $TARGET_DIR"
echo "Вывод: $OUTPUT_FILE"
[[ -n "$IGNORE_FILE" ]] && echo "Игнор: $IGNORE_FILE"
echo "-----------------"

# 1. Получение списка файлов
LIST_FILE=$(mktemp)
FILTERED_LIST=$(mktemp)

if [[ -d "$TARGET_DIR/.git" ]] && command -v git &>/dev/null; then
    echo "[1/3] Используем git index..."
    # --cached = отслеживаемые, --others = неотслеживаемые, --exclude-standard = учитываем .gitignore
    git -C "$TARGET_DIR" ls-files --cached --others --exclude-standard > "$LIST_FILE"

elif git -C "$TARGET_DIR" rev-parse --git-dir &>/dev/null 2>&1; then
    echo "[1/3] Используем git index (подпапка репозитория)..."
    (cd "$TARGET_DIR" && git ls-files --cached --others --exclude-standard) > "$LIST_FILE"

else
    echo "[1/3] Используем find..."
    find "$TARGET_DIR" -type f -not -path '*/.git/*' -printf '%P\n' > "$LIST_FILE"
fi

# Диагностика
FILES_FOUND=$(wc -l < "$LIST_FILE")
echo "    Найдено файлов: $FILES_FOUND"

if [[ "$FILES_FOUND" -eq 0 ]]; then
    echo "Ошибка: Не найдено ни одного файла в '$TARGET_DIR'" >&2
    exit 1
fi

# 2. Фильтрация
echo "[2/3] Фильтрация списка..."

# Шаг А: Оставляем только нужные расширения (или важные файлы без расширений)
grep -Ei "\.(${EXTENSIONS})$|Dockerfile|Makefile" "$LIST_FILE" | grep -v "^$(basename "$OUTPUT_FILE")$" > "$FILTERED_LIST" || true

# Шаг Б: Применяем кастомный ignore файл (если задан)
if [[ -n "$IGNORE_FILE" && -f "$IGNORE_FILE" ]]; then
    mv "$FILTERED_LIST" "${FILTERED_LIST}.tmp"
    grep -v -E '^[[:space:]]*$|^#' "$IGNORE_FILE" | \
        sed 's/\./\\./g; s/\*/.*/g' | \
        grep -v -f - "${FILTERED_LIST}.tmp" > "$FILTERED_LIST" || true
    rm -f "${FILTERED_LIST}.tmp"
fi

# Сортируем для красоты
sort -o "$FILTERED_LIST" "$FILTERED_LIST"
TOTAL=$(wc -l < "$FILTERED_LIST")

# 3. Генерация документации
echo "[3/3] Генерация $OUTPUT_FILE ($TOTAL файлов)..."

{
    echo "# Документация проекта"
    echo ""
    echo "- **Источник:** \`$(realpath "$TARGET_DIR")\`"
    echo "- **Дата:** $(date)"
    echo "- **Файлов:** $TOTAL"
    echo ""
    echo "## Структура проекта"
    echo ""
    echo '```text'
    generate_tree_view < "$FILTERED_LIST"
    echo '```'
    echo ""
    echo "---"
    echo ""
    echo "## Содержимое файлов"
    echo ""
} > "$OUTPUT_FILE"

# Читаем файлы и дописываем
while IFS= read -r rel_path; do
    full_path="$TARGET_DIR/$rel_path"

    if [[ ! -f "$full_path" ]] || ! is_text_file "$full_path"; then
        continue
    fi

    lang_tag=$(get_language_tag "$full_path")

    # Визуальный вывод прогресса
    printf "Обработка: %s \033[0K\r" "$rel_path" >&2

    {
        echo "### $rel_path"
        echo ""
        echo "\`\`\`$lang_tag"
        cat "$full_path"
        echo ""
        echo "\`\`\`"
        echo ""
    } >> "$OUTPUT_FILE"

done < "$FILTERED_LIST"

# Финал (cleanup сработает автоматически через trap)
printf "\nГотово! Файл сохранен: %s\n" "$OUTPUT_FILE"
