<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from "vue";
import BaseButton from "@/components/base/BaseButton.vue";
import BaseIcon from "@/components/base/BaseIcon.vue";
import {
  getKnowledgeGraph,
  type KnowledgeGraphNode,
  type KnowledgeGraphEdge,
  type KnowledgeGraphData,
} from "@/services/knowledge/knowledge.service";

interface SimNode extends KnowledgeGraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
}

interface SimEdge extends KnowledgeGraphEdge {
  sourceNode?: SimNode;
  targetNode?: SimNode;
}

const props = defineProps<{
  projectId: string;
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
const searchEntity = ref("");
const depth = ref(1);
const maxNodes = ref(35);
const loading = ref(false);
const error = ref("");
const rawData = ref<KnowledgeGraphData | null>(null);
const selectedNode = ref<SimNode | null>(null);

// 视图变换
const transform = ref({ x: 0, y: 0, scale: 1 });
let isDragging = false;
let isPanning = false;
let dragNode: SimNode | null = null;
let startMousePos = { x: 0, y: 0 };
let hoveredNode: SimNode | null = null;

let animationFrameId: number | null = null;
const nodes = ref<SimNode[]>([]);
const edges = ref<SimEdge[]>([]);

// 节点类型配色表
const TYPE_COLORS: Record<string, string> = {
  concept: "#3b82f6", // blue
  person: "#10b981", // emerald
  organization: "#8b5cf6", // purple
  technology: "#f59e0b", // amber
  document: "#ec4899", // pink
  unknown: "#64748b", // slate
};

function getNodeColor(type: string): string {
  const t = (type || "unknown").toLowerCase();
  for (const key of Object.keys(TYPE_COLORS)) {
    if (t.includes(key)) return TYPE_COLORS[key];
  }
  return TYPE_COLORS.unknown;
}

async function loadGraphData() {
  if (!props.projectId) return;
  loading.value = true;
  error.value = "";
  selectedNode.value = null;

  try {
    const data = await getKnowledgeGraph(props.projectId, {
      entityName: searchEntity.value,
      depth: depth.value,
      maxNodes: maxNodes.value,
    });
    rawData.value = data;

    if (data.status === "error") {
      error.value = data.message || "图谱读取异常";
      nodes.value = [];
      edges.value = [];
      return;
    }

    initSimulation(data.nodes, data.edges);
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : "获取知识图谱失败";
    nodes.value = [];
    edges.value = [];
  } finally {
    loading.value = false;
  }
}

function initSimulation(
  rawNodes: KnowledgeGraphNode[],
  rawEdges: KnowledgeGraphEdge[],
) {
  const canvas = canvasRef.value;
  const width = canvas ? canvas.width : 800;
  const height = canvas ? canvas.height : 600;

  const nodeMap = new Map<string, SimNode>();
  const simNodes: SimNode[] = rawNodes.map((n, i) => {
    // 环形初始分布
    const angle = (i / Math.max(rawNodes.length, 1)) * 2 * Math.PI;
    const r = Math.min(width, height) * 0.35;
    const node: SimNode = {
      ...n,
      x: width / 2 + r * Math.cos(angle) + (Math.random() - 0.5) * 40,
      y: height / 2 + r * Math.sin(angle) + (Math.random() - 0.5) * 40,
      vx: 0,
      vy: 0,
      radius: 18,
      color: getNodeColor(n.type),
    };
    nodeMap.set(n.name, node);
    return node;
  });

  const simEdges: SimEdge[] = [];
  for (const e of rawEdges) {
    const s = nodeMap.get(e.source);
    const t = nodeMap.get(e.target);
    if (s && t) {
      simEdges.push({
        ...e,
        sourceNode: s,
        targetNode: t,
      });
    }
  }

  nodes.value = simNodes;
  edges.value = simEdges;
  resetView();
}

function resetView() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  transform.value = {
    x: 0,
    y: 0,
    scale: 1,
  };
}

// 物理力学模拟步进
function stepSimulation() {
  const simNodes = nodes.value;
  const simEdges = edges.value;
  const canvas = canvasRef.value;
  if (!canvas || simNodes.length === 0) return;

  const cx = canvas.width / 2;
  const cy = canvas.height / 2;

  // 1. 节点间库仑斥力
  for (let i = 0; i < simNodes.length; i++) {
    for (let j = i + 1; j < simNodes.length; j++) {
      const a = simNodes[i];
      const b = simNodes[j];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const distSq = dx * dx + dy * dy || 1;
      const dist = Math.sqrt(distSq);

      if (dist < 400) {
        const force = 1800 / distSq;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }
  }

  // 2. 边的胡克引力
  for (const e of simEdges) {
    if (!e.sourceNode || !e.targetNode) continue;
    const dx = e.targetNode.x - e.sourceNode.x;
    const dy = e.targetNode.y - e.sourceNode.y;
    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const targetDist = 120;
    const force = (dist - targetDist) * 0.04;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;

    e.sourceNode.vx += fx;
    e.sourceNode.vy += fy;
    e.targetNode.vx -= fx;
    e.targetNode.vy -= fy;
  }

  // 3. 向心力与阻尼更新位置
  for (const n of simNodes) {
    if (n === dragNode) continue;
    // 弱向心力
    n.vx += (cx - n.x) * 0.005;
    n.vy += (cy - n.y) * 0.005;

    // 速度阻尼
    n.vx *= 0.82;
    n.vy *= 0.82;

    n.x += n.vx;
    n.y += n.vy;
  }
}

// Canvas 渲染
function render() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();

  // 视口变换
  ctx.translate(transform.value.x, transform.value.y);
  ctx.scale(transform.value.scale, transform.value.scale);

  const isDarkMode = document.documentElement.classList.contains("dark");

  // 1. 绘制边
  for (const e of edges.value) {
    if (!e.sourceNode || !e.targetNode) continue;
    const isHighlighted =
      hoveredNode &&
      (e.sourceNode === hoveredNode || e.targetNode === hoveredNode);

    ctx.beginPath();
    ctx.moveTo(e.sourceNode.x, e.sourceNode.y);
    ctx.lineTo(e.targetNode.x, e.targetNode.y);
    ctx.strokeStyle = isHighlighted
      ? "#3b82f6"
      : isDarkMode
        ? "rgba(148, 163, 184, 0.2)"
        : "rgba(100, 116, 139, 0.25)";
    ctx.lineWidth = isHighlighted ? 2.5 : 1;
    ctx.stroke();

    // 边上文字
    if (e.description && isHighlighted) {
      const midX = (e.sourceNode.x + e.targetNode.x) / 2;
      const midY = (e.sourceNode.y + e.targetNode.y) / 2;
      ctx.font = "10px sans-serif";
      ctx.fillStyle = isDarkMode ? "#cbd5e1" : "#475569";
      ctx.fillText(e.description.slice(0, 15), midX + 4, midY - 4);
    }
  }

  // 2. 绘制节点
  for (const n of nodes.value) {
    const isSelected = selectedNode.value === n;
    const isHovered = hoveredNode === n;

    // 外圈光晕 (高亮或选中)
    if (isSelected || isHovered) {
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.radius + 6, 0, Math.PI * 2);
      ctx.fillStyle = isSelected
        ? "rgba(59, 130, 246, 0.3)"
        : "rgba(148, 163, 184, 0.25)";
      ctx.fill();
    }

    // 实体圆球
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
    ctx.fillStyle = n.color;
    ctx.fill();
    ctx.strokeStyle = isDarkMode ? "#0f172a" : "#ffffff";
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // 实体文字标签
    ctx.font =
      isSelected || isHovered ? "bold 12px sans-serif" : "11px sans-serif";
    ctx.fillStyle = isDarkMode ? "#f1f5f9" : "#1e293b";
    ctx.textAlign = "center";
    ctx.fillText(n.name, n.x, n.y + n.radius + 14);
  }

  ctx.restore();
}

function animateLoop() {
  stepSimulation();
  render();
  animationFrameId = requestAnimationFrame(animateLoop);
}

// 坐标转换工具
function getCanvasMousePos(e: MouseEvent) {
  const canvas = canvasRef.value;
  if (!canvas) return { x: 0, y: 0 };
  const rect = canvas.getBoundingClientRect();
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  };
}

function screenToWorld(x: number, y: number) {
  return {
    x: (x - transform.value.x) / transform.value.scale,
    y: (y - transform.value.y) / transform.value.scale,
  };
}

function findNodeAt(x: number, y: number): SimNode | null {
  const world = screenToWorld(x, y);
  for (let i = nodes.value.length - 1; i >= 0; i--) {
    const n = nodes.value[i];
    const dx = world.x - n.x;
    const dy = world.y - n.y;
    if (dx * dx + dy * dy <= (n.radius + 5) * (n.radius + 5)) {
      return n;
    }
  }
  return null;
}

// 鼠标交互事件
function handleMouseDown(e: MouseEvent) {
  const pos = getCanvasMousePos(e);
  startMousePos = pos;
  const node = findNodeAt(pos.x, pos.y);

  if (node) {
    isDragging = true;
    dragNode = node;
    selectedNode.value = node;
  } else {
    isPanning = true;
  }
}

function handleMouseMove(e: MouseEvent) {
  const pos = getCanvasMousePos(e);

  if (isDragging && dragNode) {
    const world = screenToWorld(pos.x, pos.y);
    dragNode.x = world.x;
    dragNode.y = world.y;
    dragNode.vx = 0;
    dragNode.vy = 0;
  } else if (isPanning) {
    const dx = pos.x - startMousePos.x;
    const dy = pos.y - startMousePos.y;
    transform.value.x += dx;
    transform.value.y += dy;
    startMousePos = pos;
  } else {
    hoveredNode = findNodeAt(pos.x, pos.y);
    if (canvasRef.value) {
      canvasRef.value.style.cursor = hoveredNode ? "pointer" : "grab";
    }
  }
}

function handleMouseUp() {
  isDragging = false;
  isPanning = false;
  dragNode = null;
  if (canvasRef.value) {
    canvasRef.value.style.cursor = hoveredNode ? "pointer" : "grab";
  }
}

function handleWheel(e: WheelEvent) {
  e.preventDefault();
  const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
  const pos = getCanvasMousePos(e);

  const newScale = Math.max(
    0.2,
    Math.min(transform.value.scale * zoomFactor, 4),
  );
  transform.value.x =
    pos.x - (pos.x - transform.value.x) * (newScale / transform.value.scale);
  transform.value.y =
    pos.y - (pos.y - transform.value.y) * (newScale / transform.value.scale);
  transform.value.scale = newScale;
}

function handleResize() {
  const canvas = canvasRef.value;
  if (canvas && canvas.parentElement) {
    canvas.width = canvas.parentElement.clientWidth;
    canvas.height = Math.max(560, window.innerHeight - 340);
  }
}

onMounted(() => {
  handleResize();
  window.addEventListener("resize", handleResize);
  animationFrameId = requestAnimationFrame(animateLoop);
  void loadGraphData();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId);
  }
});

watch(
  () => props.projectId,
  () => {
    void loadGraphData();
  },
);
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- 顶部工坊搜索与参数工具栏 -->
    <div
      class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-surface px-5 py-3.5"
    >
      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2">
          <input
            v-model="searchEntity"
            type="text"
            placeholder="按实体名称模糊探索（留空浏览全图）..."
            class="h-9 w-64 rounded-xl border border-border bg-background px-3 text-xs text-text-main placeholder:text-text-muted focus:border-primary-500 focus:outline-hidden dark:bg-dark-900"
            @keyup.enter="loadGraphData"
          />
          <BaseButton
            variant="primary"
            size="sm"
            :disabled="loading"
            @click="loadGraphData"
          >
            <BaseIcon name="search" size="xs" />
            <span>探索</span>
          </BaseButton>
        </div>

        <div class="flex items-center gap-2 text-xs text-text-sub">
          <span>跳数 (Depth):</span>
          <select
            v-model.number="depth"
            class="rounded-lg border border-border bg-background px-2 py-1 text-xs font-semibold focus:outline-hidden"
            @change="loadGraphData"
          >
            <option :value="1">1 度邻居</option>
            <option :value="2">2 度网络</option>
            <option :value="3">3 度关联</option>
          </select>
        </div>

        <div class="flex items-center gap-2 text-xs text-text-sub">
          <span>最大节点:</span>
          <select
            v-model.number="maxNodes"
            class="rounded-lg border border-border bg-background px-2 py-1 text-xs font-semibold focus:outline-hidden"
            @change="loadGraphData"
          >
            <option :value="20">20 节点</option>
            <option :value="35">35 节点</option>
            <option :value="50">50 节点</option>
          </select>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <BaseButton variant="secondary" size="sm" @click="resetView">
          <BaseIcon name="refresh" size="xs" />
          <span>重置视角</span>
        </BaseButton>
      </div>
    </div>

    <!-- 拓扑画布与详情视窗容器 -->
    <div
      class="relative w-full overflow-hidden rounded-2xl border border-border bg-card shadow-2xs"
      style="height: calc(100vh - 300px); min-height: 560px"
    >
      <canvas
        ref="canvasRef"
        class="h-full w-full block cursor-grab active:cursor-grabbing"
        @mousedown="handleMouseDown"
        @mousemove="handleMouseMove"
        @mouseup="handleMouseUp"
        @mouseleave="handleMouseUp"
        @wheel="handleWheel"
      ></canvas>

      <!-- 图例与统计指示浮层 -->
      <div
        class="absolute bottom-4 left-4 z-10 flex flex-col gap-2 rounded-xl border border-border/80 bg-surface/90 p-3 text-[11px] shadow-sm backdrop-blur-xs"
      >
        <div class="font-semibold text-text-main flex items-center gap-1.5">
          <BaseIcon name="graph" size="xs" />
          <span
            >当前拓扑统计: {{ nodes.length }} 实体 /
            {{ edges.length }} 关系边</span
          >
        </div>
        <div class="flex items-center gap-3 text-text-muted">
          <span class="flex items-center gap-1">
            <span class="h-2.5 w-2.5 rounded-full bg-blue-500"></span> 概念
            (Concept)
          </span>
          <span class="flex items-center gap-1">
            <span class="h-2.5 w-2.5 rounded-full bg-emerald-500"></span> 人物
            (Person)
          </span>
          <span class="flex items-center gap-1">
            <span class="h-2.5 w-2.5 rounded-full bg-purple-500"></span> 组织
            (Org)
          </span>
          <span class="flex items-center gap-1">
            <span class="h-2.5 w-2.5 rounded-full bg-amber-500"></span> 技术
            (Tech)
          </span>
        </div>
      </div>

      <!-- 加载遮罩 -->
      <div
        v-if="loading"
        class="absolute inset-0 flex items-center justify-center bg-card/60 backdrop-blur-2xs"
      >
        <div
          class="flex items-center gap-2 text-xs font-semibold text-primary-600"
        >
          <div class="h-2 w-2 animate-ping rounded-full bg-primary-500"></div>
          <span>正在计算力导向图谱拓扑...</span>
        </div>
      </div>

      <!-- 节点详情侧边栏 -->
      <div
        v-if="selectedNode"
        class="absolute top-4 right-4 z-20 w-80 rounded-2xl border border-border bg-card/95 p-5 shadow-xl backdrop-blur-sm animate-in slide-in-from-right duration-200"
      >
        <div
          class="flex items-start justify-between gap-2 border-b border-border pb-3"
        >
          <div class="flex items-center gap-2">
            <span
              class="h-3.5 w-3.5 shrink-0 rounded-full"
              :style="{ backgroundColor: selectedNode.color }"
            ></span>
            <h4
              class="font-semibold text-text-main text-sm truncate max-w-[200px]"
            >
              {{ selectedNode.name }}
            </h4>
          </div>
          <button
            type="button"
            class="text-text-muted hover:text-text-main"
            @click="selectedNode = null"
          >
            <BaseIcon name="x" size="xs" />
          </button>
        </div>

        <div class="mt-3 space-y-3 text-xs">
          <div>
            <span class="text-text-muted">实体类型:</span>
            <span class="ml-2 font-mono font-semibold text-text-main">
              {{ selectedNode.type }}
            </span>
          </div>

          <div>
            <span class="text-text-muted">实体定义与描述:</span>
            <p
              class="mt-1 text-text-sub leading-relaxed bg-surface p-2.5 rounded-xl border border-border/60 max-h-48 overflow-y-auto"
            >
              {{ selectedNode.description || "暂无详细描述" }}
            </p>
          </div>
        </div>
      </div>

      <!-- 空状态浮层 -->
      <div
        v-if="!loading && nodes.length === 0"
        class="absolute inset-0 flex flex-col items-center justify-center p-6 text-center"
      >
        <div
          class="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-400 dark:bg-dark-800"
        >
          <BaseIcon name="graph" size="md" />
        </div>
        <h4 class="mt-3 text-sm font-semibold text-text-main">暂无图谱节点</h4>
        <p class="mt-1 text-xs text-text-sub max-w-sm">
          {{
            error ||
            "当前项目知识库尚未提取到相关实体关系。可先在「知识资产中枢」上传文档并完成入库解析。"
          }}
        </p>
      </div>
    </div>
  </div>
</template>
