<script lang="ts">
  let {
    title = '아직 고객이 없습니다',
    description = '고객을 등록하면 이곳에서 업무를 시작할 수 있어요.',
  }: { title?: string; description?: string } = $props();
</script>

<div class="empty-state">
  <span class="empty-icon" aria-hidden="true">◎</span>
  <h3>{title}</h3>
  <p>{description}</p>
</div>
