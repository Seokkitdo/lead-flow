<script lang="ts">
  import { Badge, Button, Field, EmptyState, Icon } from '@leadflow/ui';
  import { statuses } from '@leadflow/api-client';
  let { onclose }: { onclose: () => void } = $props();
</script>

<main class="design-system">
  <header class="design-header">
    <a href="/" class="brand"><span class="brand-mark">L</span>LeadFlow.</a><Button
      variant="secondary"
      onclick={onclose}>워크스페이스로 돌아가기</Button
    >
  </header>
  <span class="eyebrow">LEADFLOW DESIGN SYSTEM · 01</span>
  <h1>일의 흐름을 선명하게.</h1>
  <p class="design-intro">
    명확한 정보 위계, 차분한 색상, 일관된 상호작용.<br />고객과의 연결에 집중하는 업무 경험을
    만듭니다.
  </p>
  <section class="panel design-section">
    <span class="eyebrow">01 / FOUNDATION</span>
    <h2>색상과 타이포그래피</h2>
    <div class="swatches">
      {#each ['brand', 'ink', 'muted', 'canvas', 'surface', 'border', 'warning', 'danger'] as color}<div
        >
          <div class={`swatch swatch-${color}`}></div>
          <strong>{color}</strong><small>semantic token</small>
        </div>{/each}
    </div>
    <div class="type-samples">
      <h1>고객과 다음 기회를 연결하세요.</h1>
      <h2>명확한 다음 단계가 보이는 업무 공간</h2>
      <p>정보는 차분하게, 중요한 행동은 명확하게 전달합니다.</p>
      <small>보조 정보 · 한국 표준시(KST) · 14px</small>
    </div>
  </section>
  <section class="panel design-section">
    <span class="eyebrow">02 / COMPONENTS</span>
    <h2>행동과 상태</h2>
    <div class="component-row">
      <Button><Icon name="plus" size={17} />고객 등록</Button><Button variant="secondary"
        >정보 수정</Button
      ><Button variant="ghost">취소</Button><Button variant="danger">삭제 확인</Button><Button
        disabled>저장 중…</Button
      >
    </div>
    <div class="component-row">
      {#each Object.entries(statuses) as [key, label]}<Badge tone={key}>{label}</Badge>{/each}
    </div>
    <div class="form-grid">
      <Field label="고객 이름 *" hint="고객이 사용하는 이름을 입력하세요."
        ><input placeholder="이름 입력" /></Field
      ><Field label="현재 상태"
        ><select><option>신규</option><option>상담 진행 중</option></select></Field
      >
    </div>
    <p class="alert success" role="status">업무 기록을 저장했습니다.</p>
    <p class="alert error">입력 내용을 확인해 주세요. 필수 항목이 비어 있습니다.</p>
    <EmptyState />
  </section>
  <section class="panel design-section">
    <span class="eyebrow">03 / PRINCIPLES</span>
    <h2>함께 지키는 기준</h2>
    <div class="principle-grid">
      <div>
        <strong>의미로 색상을 선택합니다</strong>
        <p>브랜드, 본문, 상태, 경계선 토큰으로 화면을 구성합니다.</p>
      </div>
      <div>
        <strong>정보와 행동을 구분합니다</strong>
        <p>현재 상태는 배지로, 업무 활동은 누적된 기록으로 표현합니다.</p>
      </div>
      <div>
        <strong>누구나 편하게 사용합니다</strong>
        <p>명확한 레이블, 키보드 포커스, 모바일 상세 화면을 제공합니다.</p>
      </div>
    </div>
  </section>
</main>
