// HELPER: Recursive JSON Parser
const safeParseProps = (input: any): any => {
  if (!input) return {};
  if (typeof input === 'object') return input; // It's already an object
  try {
    const parsed = JSON.parse(input);
    // RECURSIVE CHECK: If the result is STILL a string, parse again.
    if (typeof parsed === 'string') return safeParseProps(parsed);
    return parsed;
  } catch (e) {
    console.error("Failed to parse props:", input);
    return {};
  }
};

// HELPER: Smart Title Casing
const toTitleCase = (str: string) => {
  if (!str) return "";
  return str.toLowerCase().split(' ').map(word => {
    // Ignore small words unless it's the first word
    if (['a', 'an', 'the', 'in', 'on', 'at', 'for', 'of', 'is'].includes(word)) return word;
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(' ');
};

import { useRef, useEffect, useState } from 'react';
import { SlidersHorizontal, X, HelpCircle } from 'lucide-react';

// V28: PULSE ANIMATION - Critical memories breathe
let pulsePhase = 0;
const PULSE_SPEED = 0.05;

// V28: TEMPORAL HEAT - Calculate memory "warmth" based on recency
const calculateTemporalHeat = (createdAt: string, lastAccessed?: string): number => {
  const now = Date.now();
  const created = new Date(createdAt).getTime();
  const accessed = lastAccessed ? new Date(lastAccessed).getTime() : created;
  
  // Use most recent interaction
  const lastInteraction = Math.max(created, accessed);
  const daysSince = (now - lastInteraction) / (1000 * 60 * 60 * 24);
  
  // Heat decays over 30 days (1.0 = hot/recent, 0.0 = cold/old)
  return Math.max(0, 1 - (daysSince / 30));
};


interface Node {
  id: string;
  label: string;
  type: 'memory' | 'entity' | 'signal' | 'cluster' | 'session' | 'anchor';
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number | null;
  fy?: number | null;
  radius: number;
  degree?: number; // Connection count for LOD
  properties?: {
    description?: string;
    created_at?: string;
  };
  full_data?: any; // Full node data for inspector
  color?: string; // DNA-mapped color from memory_type
  opacity?: number; // DNA-mapped opacity from status
  importance?: number; // DNA-mapped importance (1-10)
  memoryType?: string; // DNA-mapped memory type
  layer?: 'self' | 'world' | 'intent'; // V3 Schema
  sublayer?: string; // V3 Schema 9 types
  short_label?: string; // DNA-mapped short label
  originalLabel?: string; // Original full label
  ring?: string; // V5 Topology
  knowledgeType?: string; // V5 Topology
  topic?: string; // V5 Topology
  signalType?: 'topic' | 'knowledge_type' | 'ring' | 'unknown';
  signalValue?: string;
  env?: 'production' | 'test';
  processingStatus?: string;
}

interface Edge {
  source: string;
  target: string;
  type?: string;
  label?: string;
  similarity?: number;
}

interface GraphData {
  nodes: any[];
  edges: any[];
}

interface GraphCanvasProps {
  space: string;
  searchTerm: string;
  onSearchTermChange?: (value: string) => void;
  environment?: 'all' | 'production' | 'test';
  status?: 'all' | 'processed' | 'unprocessed';
  hideTestArtifacts?: boolean;
  onGraphStats?: (stats: { memories: number; signalCoverage: number; avgConnections: number }) => void;
  command?: { type: 'zoomIn' | 'zoomOut' | 'resetView'; nonce: number } | null;
}

  // VIEW-LAYER LABEL CLEANER
  const getCleanTitle = (node: any) => {
    // Priority: Short Label -> Parsed Title -> Raw Label
    let text = node.short_label || node.full_data?.parsed_props?.title || node.label || "Memory";
    
    // A. SPLIT COLON (Force Split)
    if (text.includes(':')) text = text.split(':')[0];
    
    // B. REMOVE NOISE
    text = text.replace(/^(User|The)\s+(is a|has|preference|is|values)\s?/i, '');
    text = text.replace(/^User\s/i, '');
    
    // C. TITLE CASE
    return toTitleCase(text.trim());
  };

const GraphCanvas: React.FC<GraphCanvasProps> = ({
  space,
  searchTerm,
  onSearchTermChange,
  environment = 'all',
  status = 'all',
  hideTestArtifacts = true,
  onGraphStats,
  command
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<GraphData>({ nodes: [], edges: [] });
  const nodesRef = useRef<Node[]>([]);
  const edgesRef = useRef<Edge[]>([]);
  const requestRef = useRef<number>();
  
  // Interaction state
  const [hoveredNode, setHoveredNode] = useState<Node | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<Edge | null>(null);
  const [focusedNode, setFocusedNode] = useState<Node | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  // Story Focus: restrict the canvas to a readable neighborhood around a node.
  const [storyFocusOn, setStoryFocusOn] = useState(false);
  const [storyFocusNode, setStoryFocusNode] = useState<Node | null>(null);
  const [visibleTypes, setVisibleTypes] = useState({
    memory: true,
    signal: false, // V1.6.2: Hide signal hubs by default - they clutter the solar system view
    entity: false, // PURE THOUGHT MODE: Hide entities by default, show only memory mesh
    cluster: false,
    session: false
  });
  const [viewMode, setViewMode] = useState<'v3' | 'v5'>('v5');

  const [controlsOpen, setControlsOpen] = useState(false);

  // Keyboard shortcuts (global)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      setFocusedNode(null);
      setSelectedNode(null);
      setControlsOpen(false);
      onSearchTermChange?.('');
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onSearchTermChange]);

  const [visibleSignalKinds, setVisibleSignalKinds] = useState({
    topic: true,
    knowledge_type: true,
    ring: true,
  });
  const [showSignalEdges, setShowSignalEdges] = useState(true);
  const [showCohesionEdges, setShowCohesionEdges] = useState(true);
  const [showSemanticEdges, setShowSemanticEdges] = useState(false);

  // Mirror dynamic UI state/props into refs so the RAF loop always sees latest values
  const hoveredEdgeRef = useRef<Edge | null>(null);
  const hoveredNodeRef = useRef<Node | null>(null);
  const focusedNodeRef = useRef<Node | null>(null);
  const storyFocusOnRef = useRef(storyFocusOn);
  const storyFocusNodeRef = useRef<Node | null>(storyFocusNode);
  const searchTermRef = useRef<string>(searchTerm);
  const visibleTypesRef = useRef(visibleTypes);
  const visibleSignalKindsRef = useRef(visibleSignalKinds);
  const showSignalEdgesRef = useRef(showSignalEdges);
  const showCohesionEdgesRef = useRef(showCohesionEdges);
  const showSemanticEdgesRef = useRef(showSemanticEdges);
  const environmentRef = useRef(environment);
  const statusRef = useRef(status);
  const viewModeRef = useRef(viewMode);

  useEffect(() => {
    hoveredEdgeRef.current = hoveredEdge;
  }, [hoveredEdge]);

  useEffect(() => {
    hoveredNodeRef.current = hoveredNode;
  }, [hoveredNode]);

  useEffect(() => {
    focusedNodeRef.current = focusedNode;
  }, [focusedNode]);

  useEffect(() => {
    storyFocusOnRef.current = storyFocusOn;
  }, [storyFocusOn]);

  useEffect(() => {
    storyFocusNodeRef.current = storyFocusNode;
  }, [storyFocusNode]);

  useEffect(() => {
    searchTermRef.current = searchTerm;
  }, [searchTerm]);

  useEffect(() => {
    visibleTypesRef.current = visibleTypes;
  }, [visibleTypes]);

  useEffect(() => {
    visibleSignalKindsRef.current = visibleSignalKinds;
  }, [visibleSignalKinds]);

  useEffect(() => {
    showSignalEdgesRef.current = showSignalEdges;
  }, [showSignalEdges]);

  useEffect(() => {
    showCohesionEdgesRef.current = showCohesionEdges;
  }, [showCohesionEdges]);

  useEffect(() => {
    showSemanticEdgesRef.current = showSemanticEdges;
  }, [showSemanticEdges]);

  useEffect(() => {
    environmentRef.current = environment;
  }, [environment]);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  useEffect(() => {
    viewModeRef.current = viewMode;
  }, [viewMode]);
  const draggingNode = useRef<Node | null>(null);
  const offset = useRef({ x: 0, y: 0 }); // Pan offset
  const scale = useRef(1); // Zoom scale
  const isDraggingCanvas = useRef(false);

  // External zoom/reset commands from App
  useEffect(() => {
    if (!command) return;

    if (command.type === 'resetView') {
      scale.current = 1;
      offset.current = { x: 0, y: 0 };
      return;
    }

    const zoomFactor = command.type === 'zoomIn' ? 1.15 : 1 / 1.15;
    const nextScale = Math.max(0.1, Math.min(5, scale.current * zoomFactor));
    scale.current = nextScale;
  }, [command?.nonce]);
  
  // Meaningful metrics for users
  const [graphStats, setGraphStats] = useState({
    memories: 0,
    signalCoverage: 0, // % of memories connected to signal hubs
    avgConnections: 0,
    visibleNodes: 0,
    visibleEdges: 0,
    edgeTypeCounts: {} as Record<string, number>,
  });
  const lastMousePos = useRef({ x: 0, y: 0 });

  const computeVisibleGraphStats = () => {
    const nodes = nodesRef.current || [];
    const edges = edgesRef.current || [];

    let activeNodes = nodes
      .filter((n: any) => !!visibleTypes[n.type as keyof typeof visibleTypes])
      .filter((n: any) => {
        if (n.type !== 'memory') return true;

        if (hideTestArtifacts) {
          const label = (n.originalLabel || n.short_label || n.label || '').toString().toLowerCase();
          const content = (n.full_data?.properties?.content || n.full_data?.description || '').toString().toLowerCase();
          const isArtifact =
            content.startsWith('elefante e2e test memory') ||
            content.startsWith('hybrid search test memory') ||
            content.startsWith('entity relationship test ') ||
            content.startsWith('persistence test ') ||
            label.startsWith('e2e-test') ||
            label.startsWith('entity relationship test') ||
            label.startsWith('persistence test') ||
            label.includes('hybrid_test_');
          if (isArtifact) return false;
        }

        if (environment !== 'all' && n.env !== environment) return false;

        if (status === 'all') return true;
        const statusValue = String(n.processingStatus || '').toLowerCase();
        const isProcessed = statusValue === 'processed' || statusValue === 'done' || statusValue === 'complete';
        if (status === 'processed') return isProcessed;
        if (status === 'unprocessed') return !isProcessed;
        return true;
      })
      .filter((n: any) => {
        if (n.type !== 'signal') return true;
        const kind = (n.signalType || 'unknown') as keyof typeof visibleSignalKinds | 'unknown';
        if (kind === 'unknown') return true;
        return !!(visibleSignalKinds as any)[kind];
      });

    // Apply Story Focus to metrics too (match render-loop neighborhood selection).
    if (storyFocusOn && storyFocusNode?.id) {
      const focusId = storyFocusNode.id;
      const preIds = new Set(activeNodes.map((n: any) => n.id));
      const preById = new Map(activeNodes.map((n: any) => [n.id, n] as const));

      const incident = edges
        .filter((e: any) => preIds.has(e.source) && preIds.has(e.target))
        .filter((e: any) => e.source === focusId || e.target === focusId);

      const allowed = new Set<string>();
      allowed.add(focusId);

      // Always keep directly-connected signal hubs.
      incident.forEach((e: any) => {
        const otherId = e.source === focusId ? e.target : e.source;
        const other = preById.get(otherId);
        if (other?.type === 'signal') allowed.add(otherId);
      });

      const weight = (e: any): number => {
        const t = String(e.type || 'graph');
        const lbl = String(e.label || '');
        if (t === 'supersession') return 100;
        if (t === 'cohesion') {
          if (lbl === 'CO_TOPIC') return 95;
          if (lbl === 'CO_KNOWLEDGE_TYPE') return 85;
          if (lbl === 'CO_RING') return 75;
          return 70;
        }
        if (t === 'graph') return 60;
        if (t === 'semantic') return 50 + (typeof e.similarity === 'number' ? e.similarity : 0);
        return 40;
      };

      const candidates: Array<{ id: string; w: number }> = [];
      incident.forEach((e: any) => {
        const otherId = e.source === focusId ? e.target : e.source;
        const other = preById.get(otherId);
        if (!other || other.type !== 'memory') return;
        candidates.push({ id: otherId, w: weight(e) });
      });
      candidates.sort((a, b) => b.w - a.w);
      const seen = new Set<string>();
      const top = candidates.filter(c => (seen.has(c.id) ? false : (seen.add(c.id), true))).slice(0, 18);
      top.forEach(t => allowed.add(t.id));

      // Also keep the signals of those top neighbors for context.
      const neighborIds = new Set(top.map(t => t.id));
      edges
        .filter((e: any) => preIds.has(e.source) && preIds.has(e.target))
        .filter((e: any) =>
          (neighborIds.has(e.source) && preById.get(e.target)?.type === 'signal') ||
          (neighborIds.has(e.target) && preById.get(e.source)?.type === 'signal')
        )
        .forEach((e: any) => {
          allowed.add(e.source);
          allowed.add(e.target);
        });

      activeNodes = activeNodes.filter((n: any) => allowed.has(n.id));
    }

    const activeNodeIds = new Set(activeNodes.map((n: any) => n.id));
    const nodeById = new Map(activeNodes.map((n: any) => [n.id, n] as const));

    const activeEdges = edges
      .filter((e: any) => activeNodeIds.has(e.source) && activeNodeIds.has(e.target))
      .filter((e: any) => {
        if (e.type === 'semantic') return !!showSemanticEdges;
        if (e.type === 'cohesion') return !!showCohesionEdges;
        if (e.type === 'signal') {
          if (!visibleTypes.signal || !showSignalEdges) return false;
          const a = nodeById.get(e.source);
          const b = nodeById.get(e.target);
          const signalNode = a?.type === 'signal' ? a : (b?.type === 'signal' ? b : null);
          if (!signalNode) return true;
          const kind = (signalNode.signalType || 'unknown') as keyof typeof visibleSignalKinds | 'unknown';
          if (kind === 'unknown') return true;
          return !!(visibleSignalKinds as any)[kind];
        }
        if (e.type === 'cluster' || e.type === 'cluster_backbone') return !!visibleTypes.cluster;
        return true;
      });

    const memNodes = activeNodes.filter((n: any) => n.type === 'memory');
    const memCount = memNodes.length;

    const edgeTypeCounts: Record<string, number> = {};
    activeEdges.forEach((e: any) => {
      const t = String(e.type || 'graph');
      edgeTypeCounts[t] = (edgeTypeCounts[t] || 0) + 1;
    });

    const signalEdges = activeEdges.filter((e: any) => e.type === 'signal');
    const memsWithSignals = new Set<string>();
    signalEdges.forEach((e: any) => {
      const a = nodeById.get(e.source);
      const b = nodeById.get(e.target);
      if (a?.type === 'memory') memsWithSignals.add(String(e.source));
      if (b?.type === 'memory') memsWithSignals.add(String(e.target));
    });
    const coverage = memCount > 0 ? Math.round((memsWithSignals.size / memCount) * 100) : 0;
    const avgConn = memCount > 0 ? (activeEdges.length / memCount) : 0;

    const stats = {
      memories: memCount,
      signalCoverage: coverage,
      avgConnections: parseFloat(avgConn.toFixed(1)),
      visibleNodes: activeNodes.length,
      visibleEdges: activeEdges.length,
      edgeTypeCounts,
    };
    setGraphStats(stats);
    onGraphStats?.({ memories: stats.memories, signalCoverage: stats.signalCoverage, avgConnections: stats.avgConnections });
  };

  // Fetch Data
  useEffect(() => {
    const fetchData = async () => {
      try {
        // CACHE BUSTING: Force fresh network request
        const res = await fetch(`/api/graph?limit=500&space=${space === 'all' ? '' : space}&t=${Date.now()}`);
        const json = await res.json();
        
        // Silent: API data loaded
        
        // Initialize positions randomly
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        // --- BEGIN GUILLOTINE PROTOCOL V3 ---
        // 1. Define Allowed Nodes (Filter out User ENTITY only, keep memory nodes)
        const allowedNodes = json.nodes.filter((n: any) => {
          const label = (n.label || '').toLowerCase().trim();
          const entityType = (n.entityType || '').toLowerCase();
          const type = (n.type || '').toLowerCase();
          
          // ONLY exclude User entity nodes (not memory nodes about user)
          const isUserEntity = (label === 'user' && type === 'entity') ||
                               (entityType === 'person' && type === 'entity') ||
                               (type === 'person');
          
          if (isUserEntity) {
            console.log("🚫 GUILLOTINE V3: Removing User Entity:", n.label, "ID:", n.id);
          }
          return !isUserEntity;
        });
        
        const allowedNodeIds = new Set(allowedNodes.map((n: any) => n.id));
        console.log(`✂️ Nodes after guillotine: ${json.nodes.length} → ${allowedNodes.length}`);
        
        if (viewMode === 'v3') {
          // V3 HIERARCHY: Inject Anchor Nodes
          // Triangulate around center
          const cx = width / 2;
          const cy = height / 2;
          const anchors = [
            { id: 'v3_anchor_intent', label: 'INTENT', type: 'anchor', layer: 'intent', x: cx, y: cy - 250, fx: cx, fy: cy - 250, color: '#FFFFFF', radius: 30, importance: 10 },
            { id: 'v3_anchor_self', label: 'SELF', type: 'anchor', layer: 'self', x: cx - 250, y: cy + 150, fx: cx - 250, fy: cy + 150, color: '#EF4444', radius: 30, importance: 10 },
            { id: 'v3_anchor_world', label: 'WORLD', type: 'anchor', layer: 'world', x: cx + 250, y: cy + 150, fx: cx + 250, fy: cy + 150, color: '#3B82F6', radius: 30, importance: 10 }
          ];
          
          // Add anchors if not present
          anchors.forEach(anchor => {
               if (!allowedNodes.find((n:any) => n.id === anchor.id)) {
                   allowedNodes.push(anchor);
                   allowedNodeIds.add(anchor.id); // Valid target for edges? maybe not.
               }
          });
        }
        
        // 2. Strict Edge Scrubbing (BOTH ends must exist in allowedNodes)
        const cleanEdges = json.edges.filter((e: any) => {
            // Handle D3 object references vs String IDs
            const s = typeof e.source === 'object' ? e.source.id : e.source;
            const t = typeof e.target === 'object' ? e.target.id : e.target;
            
            // ONLY keep edge if BOTH ends exist in allowedNodes
            const bothEndsValid = allowedNodeIds.has(s) && allowedNodeIds.has(t);
            return bothEndsValid;
        });
        
        console.log(`✂️ Edges after guillotine: ${json.edges.length} → ${cleanEdges.length} (removed ${json.edges.length - cleanEdges.length} dangling edges)`);
        // --- END GUILLOTINE PROTOCOL V2 ---
        
        // Calculate degree (connection count) for each node using clean edges
        const degreeMap = new Map<string, number>();
        cleanEdges.forEach((e: any) => {
          const source = e.source || e.from;
          const target = e.target || e.to;
          degreeMap.set(source, (degreeMap.get(source) || 0) + 1);
          degreeMap.set(target, (degreeMap.get(target) || 0) + 1);
        });
        
        // 4. SPRINT 7: KEYWORD-BASED COLOR HEURISTICS (REMOVED - Now using v27 color spectrum)
        
        const processedNodes = allowedNodes.map((n: any) => {
          try {
            // SPRINT 22: DEEP PARSING - Recursive JSON parser
            const fullData = n.full_data || {};
            
            // FORCE PARSE PROPS (Fixes "Fact/5/Neutral" bug)
            const props = safeParseProps(fullData.props);
            
            // Update the node's reference to the parsed props so the Sidebar sees it
            if (!n.full_data) n.full_data = {};
            n.full_data.parsed_props = props; // Store it safely
            
            
            
            // Debug first node
            if (n.id === allowedNodes[0]?.id) {
              console.log("🔍 FIRST NODE PROPS:", props);
            }
          
          // V27.0 SEMANTIC TOPOLOGY: ORBITAL HIERARCHY
          // FIX: Check BOTH n.properties (API snapshot) and props (full_data.props)
          const importance = props.importance || n.properties?.importance || 5;
          const layer = props.layer || n.properties?.layer || 'world';
          const sublayer = props.sublayer || n.properties?.sublayer || 'fact';
          const ring = props.ring || n.properties?.ring || 'leaf';
          const knowledgeType = props.knowledge_type || n.properties?.knowledge_type || props.memory_type || n.properties?.memory_type || 'unknown';
          const topic = props.topic || n.properties?.topic || '';

          // SIGNAL HUB DETECTION (snapshot signal:* hubs)
          const rawSignalType = (props.signal_type || n.properties?.signal_type || '').toString();
          const isSignal = String(n.id || '').startsWith('signal:') || !!rawSignalType;
          const signalType: 'topic' | 'knowledge_type' | 'ring' | 'unknown' =
            rawSignalType === 'topic' || rawSignalType === 'knowledge_type' || rawSignalType === 'ring'
              ? rawSignalType
              : (isSignal ? 'unknown' : 'unknown');
          const signalValue = (props.value || n.properties?.value || '').toString();

          const tagsRaw = props.tags || n.properties?.tags || [];
          const tags: string[] = Array.isArray(tagsRaw)
            ? tagsRaw.map((t: any) => String(t))
            : typeof tagsRaw === 'string'
              ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean)
              : [];
          const env: 'production' | 'test' = tags.some(t => t.toLowerCase().includes('test')) ? 'test' : 'production';
          const processingStatus =
            props.processing_status ||
            n.properties?.processing_status ||
            props.processingStatus ||
            n.properties?.processingStatus ||
            '';
          
          // Debug: Log layer/sublayer for first node
          if (n.id === allowedNodes[0]?.id) {
            console.log("🎨 COLOR DEBUG:", { layer, sublayer, propsLayer: props.layer, nodePropsLayer: n.properties?.layer });
          }
          
          // SIZE: POWER LAW HIERARCHY (User Request: "Nodes bigger... confusing")
          // Formula: r = Base + (Importance^2 * Factor)
          // Imp 1:  8 + 0.4  = 8.4px  (Detail)
          // Imp 5:  8 + 10   = 18px   (Concept)
          // Imp 8:  10 + 12 = 22px (Core)
          // Imp 10: 10 + 15 = 25px (Landmark)
          // CEO DIRECTIVE: Linear scaling for "Neural Web" balance
          let radius = 10 + (importance * 1.5);
          
           // COLOR:
           // - V3: Layer-aware gradients
           // - V5: RING-BASED coloring (visual hierarchy)
           let color = '#3b82f6'; // Default Blue

           if (n.type === 'memory') {
            if (viewMode === 'v5') {
              // V1.6.2: COLOR BY RING (not knowledge_type) - Makes hierarchy VISIBLE
              const r = String(ring || 'leaf').toLowerCase();
              if (r === 'core') color = '#F59E0B';        // Amber/Gold - Sun
              else if (r === 'domain') color = '#06B6D4'; // Cyan - Planets
              else if (r === 'topic') color = '#A855F7';  // Purple - Moons
              else color = '#3B82F6';                      // Blue - Asteroids (leaf)
            } else {
              if (layer === 'self') {
                switch(sublayer) {
                  case 'identity': color = '#EF4444'; break; // Red
                  case 'preference': color = '#F97316'; break; // Orange
                  case 'constraint': color = '#EAB308'; break; // Yellow
                  default: color = '#F97316'; // Fallback
                }
              } else if (layer === 'world') {
                switch(sublayer) {
                  case 'fact': color = '#3B82F6'; break; // Blue
                  case 'failure': color = '#7C3AED'; break; // Purple
                  case 'method': color = '#10B981'; break; // Green
                  default: color = '#3B82F6'; // Fallback
                }
              } else if (layer === 'intent') {
                switch(sublayer) {
                  case 'rule': color = '#FFFFFF'; break; // White (Stark)
                  case 'goal': color = '#22C55E'; break; // Toxic Green
                  case 'anti-pattern': color = '#F43F5E'; break; // Rose
                  default: color = '#FFFFFF'; // Fallback
                }
              } else {
                // Fallback for legacy memories
                color = '#94A3B8'; // Slate
              }
            }
           } else {
            // Non-memory nodes: differentiate signal hubs vs generic entities.
            if (isSignal) {
              if (signalType === 'topic') color = '#22D3EE'; // cyan
              else if (signalType === 'knowledge_type') color = '#A855F7'; // purple
              else if (signalType === 'ring') color = '#F59E0B'; // amber
              else color = '#E2E8F0'; // slate-200
            } else {
              color = n.type === 'entity' ? '#E6E6FA' : '#FFD700';
            }
           }

          if (isSignal) {
            radius = 12;
          }
          
          // OPACITY: Handle "Redundant" status
          const opacity = props.status === 'redundant' ? 0.5 : 1.0;
          
          // SPRINT 20: CONSISTENT LABELS - Single source of truth
          // 1. Get best available raw title
          let rawTitle = props.cognitive_analysis?.title || props.title || n.label || "Memory";
          if (isSignal) {
            const kind = rawSignalType || (String(n.id || '').split(':')[1] || 'signal');
            const value = signalValue || '';
            rawTitle = value ? `${kind}: ${value}` : String(n.label || rawTitle);
          }
          
          // 2. SPLIT AT COLON (Critical Step)
          // "IMPORTANCE SCALE CALIBRATION: Correct usage..." -> "IMPORTANCE SCALE CALIBRATION"
          let cleanLabel = isSignal ? rawTitle.trim() : rawTitle.split(':')[0].trim();
          
          // 3. Remove noisy prefixes
          if (!isSignal) {
            cleanLabel = cleanLabel.replace(/^(User|The)\s+(is a|has|preference|is|values)\s?/i, '');
            cleanLabel = cleanLabel.replace(/^User\s/i, '');
          }
          
          // 4. Apply TITLE CASE
          cleanLabel = isSignal ? cleanLabel : toTitleCase(cleanLabel);
          
          // Emoji prefix
          const v3Emoji = layer === 'self' ? '🔴' : layer === 'intent' ? '⚪' : '🔵';
          const v5Emoji = ring === 'core' ? '⭐' : ring === 'domain' ? '🟣' : ring === 'topic' ? '🔷' : '⚪';
          const prefixEmoji = viewMode === 'v5' ? v5Emoji : v3Emoji;
          
          // 6. Create two versions
          const shortLabel = isSignal ? cleanLabel : cleanLabel; // Full clean title for sidebar
          const prefix = isSignal ? '⬡' : prefixEmoji;
          const canvasLabel = cleanLabel.length > 22
            ? `${prefix} ${cleanLabel.substring(0, 20)}…`
            : `${prefix} ${cleanLabel}`;
          
          return {
            ...n,
            type: isSignal ? 'signal' : n.type,
            label: canvasLabel, // Truncated for canvas
            originalLabel: n.label,
            short_label: shortLabel, // Full clean title for sidebar
            canvas_label: canvasLabel, // Explicit canvas label
            x: Math.random() * width,
            y: Math.random() * height,
            vx: 0,
            vy: 0,
            radius: radius,
            color: color,
            opacity: opacity,
            degree: degreeMap.get(n.id) || 0,
            importance: importance,
            memoryType: props.memory_type || 'fact',
            layer: layer, // V3
            sublayer: sublayer, // V3
            ring: ring, // V5
            knowledgeType: knowledgeType, // V5
            topic: topic, // V5
            signalType: isSignal ? signalType : undefined,
            signalValue: isSignal ? signalValue : undefined,
            env,
            processingStatus
          };
          } catch (error) {
            console.error("❌ Error processing node:", n.id, error);
            // Return minimal node on error
            return {
              ...n,
              label: n.label || 'Error',
              short_label: n.label || 'Error',
              x: Math.random() * width,
              y: Math.random() * height,
              vx: 0,
              vy: 0,
              radius: 12,
              color: '#EF4444',
              opacity: 1.0,
              degree: 0,
              importance: 5,
              memoryType: 'fact'
            };
          }
        });
        
        // Keep all edges; filtering happens at render-time based on visible node/edge toggles.
        const allLinks = cleanEdges;
        
        // SPRINT 24: ORBITAL TELEPORT - Hard-code orphan positions
        const connectedIds = new Set<string>();
        allLinks.forEach((link: any) => {
          connectedIds.add(typeof link.source === 'object' ? link.source.id : link.source);
          connectedIds.add(typeof link.target === 'object' ? link.target.id : link.target);
        });
        
        // Separate orphans and cluster
        const orphans = processedNodes.filter((n: any) => !connectedIds.has(n.id));
        const cluster = processedNodes.filter((n: any) => connectedIds.has(n.id));
        
        // Processing complete
        
        // Layout
        const canvas = canvasRef.current;
        if (canvas) {
          const width = canvas.width;
          const height = canvas.height;
          const centerX = width / 2;
          const centerY = height / 2;

          if (viewMode === 'v5') {
            // V1.6.2: RADII match visual ring guides
            const ringRadii: Record<string, number> = {
              core: 50,      // Center zone
              domain: 180,   // Inner orbit
              topic: 300,    // Middle orbit
              leaf: 420      // Outer orbit
            };

            const memoryNodes = processedNodes.filter((n: any) => n.type === 'memory');
            const byRing = new Map<string, any[]>();
            memoryNodes.forEach((node: any) => {
              const r = String(node.ring || node.properties?.ring || 'leaf');
              if (!byRing.has(r)) byRing.set(r, []);
              byRing.get(r)!.push(node);
            });

            for (const [ringName, ringNodes] of byRing.entries()) {
              const radius = ringRadii[ringName] ?? ringRadii.leaf;
              const angleStep = (2 * Math.PI) / Math.max(1, ringNodes.length);
              // V1.6.2: More jitter for visual interest, but keep within ring zone
              const jitterRange = ringName === 'core' ? 30 : (ringName === 'domain' ? 40 : 60);

              ringNodes.forEach((node: any, i: number) => {
                const angle = i * angleStep + (Math.random() - 0.5) * 0.3; // Angle jitter
                const jitter = (Math.random() - 0.5) * jitterRange;
                const r = radius + jitter;

                const targetX = centerX + Math.cos(angle) * r;
                const targetY = centerY + Math.sin(angle) * r;

                node.x = targetX;
                node.y = targetY;
                // V1.6.3: NEURAL WEB - No locking. Everything floats.
                // Core is no longer locked.
                node.fx = null;
                node.fy = null;
                node.vx = 0;
                node.vy = 0;
              });
            }

            // V1.6.2: HIDE signal hubs in V5 mode - they clutter the view
            // Memories ARE the nodes; signals are redundant meta-clusters
            const signalNodes = processedNodes.filter((n: any) => n.type === 'signal');
            signalNodes.forEach((node: any) => {
              // Move far off-screen (will be filtered by visibility anyway)
              node.x = -9999;
              node.y = -9999;
              node.fx = -9999;
              node.fy = -9999;
            });
          } else if (orphans.length > 0) {
            // SPRINT 25: ORBITAL ANCHOR - Lock orphans with fx/fy
            const radius = 300; // Reduced to 300px for safer viewport fit
            const angleStep = (2 * Math.PI) / orphans.length;
            
            orphans.forEach((node: any, i: number) => {
              const angle = i * angleStep;
              
              // CALCULATE POSITION
              const targetX = centerX + Math.cos(angle) * radius;
              const targetY = centerY + Math.sin(angle) * radius;
              
              // TELEPORT (Current Position)
              node.x = targetX;
              node.y = targetY;
              
              // ANCHOR (Physics Lock)
              node.fx = targetX;
              node.fy = targetY;
              
              // Kill Velocity
              node.vx = 0;
              node.vy = 0;
            });
            
            // UNLOCK The Cluster (Ensure center nodes can still move)
            cluster.forEach((node: any) => {
              node.fx = null; // Let physics handle the semantic mesh
              node.fy = null;
            });
            
            console.log(`⚓ Anchored ${orphans.length} orphans to ring at radius ${radius}px (PHYSICS LOCKED)`);
          }
        }
          
          const newNodes = processedNodes;
          
          // Compute user-meaningful metrics
          const memCount = newNodes.filter((n: any) => n.type === 'memory').length;
          const signalEdges = allLinks.filter((e: any) => e.type === 'signal');
          const memsWithSignals = new Set<string>();
          signalEdges.forEach((e: any) => {
            if (newNodes.find((n: any) => n.id === e.source && n.type === 'memory')) memsWithSignals.add(e.source);
            if (newNodes.find((n: any) => n.id === e.target && n.type === 'memory')) memsWithSignals.add(e.target);
          });
          const coverage = memCount > 0 ? Math.round((memsWithSignals.size / memCount) * 100) : 0;
          const avgConn = memCount > 0 ? (allLinks.length / memCount).toFixed(1) : '0';
          setGraphStats({ memories: memCount, signalCoverage: coverage, avgConnections: parseFloat(avgConn), visibleNodes: newNodes.length, visibleEdges: allLinks.length, edgeTypeCounts: {} });
          onGraphStats?.({ memories: memCount, signalCoverage: coverage, avgConnections: parseFloat(avgConn) });
          
          nodesRef.current = newNodes;
          edgesRef.current = allLinks;
          setData({nodes: newNodes, edges: allLinks});
      } catch (err) {
        console.error("Failed to fetch graph", err);
      }
    };
    
    fetchData();
  }, [space, viewMode]);

  // Recompute visible graph metrics when filters/toggles change.
  useEffect(() => {
    computeVisibleGraphStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    hideTestArtifacts,
    environment,
    status,
    visibleTypes,
    visibleSignalKinds,
    showSignalEdges,
    showCohesionEdges,
    showSemanticEdges,
  ]);

  // Simulation & Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const animate = () => {
      const width = canvas.width;
      const height = canvas.height;
      
      // 1. Physics Step
      const nodes = nodesRef.current;
      const edges = edgesRef.current;

      // Live UI state/props (avoids stale closures)
      const hoveredEdge = hoveredEdgeRef.current;
      const focusedNode = focusedNodeRef.current;
      const hoveredNode = hoveredNodeRef.current;
      const searchTerm = searchTermRef.current;
      const visibleTypes = visibleTypesRef.current;
      const visibleSignalKinds = visibleSignalKindsRef.current;
      const showSignalEdges = showSignalEdgesRef.current;
      const showCohesionEdges = showCohesionEdgesRef.current;
      const showSemanticEdges = showSemanticEdgesRef.current;
      const storyFocusOn = storyFocusOnRef.current;
      const storyFocusNode = storyFocusNodeRef.current;
      const environment = environmentRef.current;
      const status = statusRef.current;
      const viewMode = viewModeRef.current;

      // "Touch focus": if no locked focus (shift+click), hovering temporarily focuses.
      const activeFocusNode = focusedNode || hoveredNode;

      const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
      const edgeBaseStrength = (edge: Edge): number => {
        if (edge.type === 'semantic') {
          return clamp01(typeof edge.similarity === 'number' ? edge.similarity : 0.55);
        }
        if (edge.type === 'signal') return 0.75;
        if (edge.type === 'cohesion') return 0.55;
        if (edge.type === 'supersession') return 0.9;
        if (edge.type === 'cluster_backbone') return 0.35;
        if (edge.type === 'cluster') return 0.25;
        // Kuzu graph edges or unknown
        return 0.5;
      };

      // Visibility filtering (used for physics, rendering, focus adjacency)
      let activeNodes = nodes
        .filter(n => !!visibleTypes[n.type as keyof typeof visibleTypes])
        .filter(n => {
          if (n.type !== 'memory') return true;

          if (hideTestArtifacts) {
            const label = (n.originalLabel || n.short_label || n.label || '').toString().toLowerCase();
            const content = (n.full_data?.properties?.content || n.full_data?.description || '').toString().toLowerCase();
            const isArtifact =
              content.startsWith('elefante e2e test memory') ||
              content.startsWith('hybrid search test memory') ||
              content.startsWith('entity relationship test ') ||
              content.startsWith('persistence test ') ||
              label.startsWith('e2e-test') ||
              label.startsWith('entity relationship test') ||
              label.startsWith('persistence test') ||
              label.includes('hybrid_test_');
            if (isArtifact) return false;
          }

          if (environment !== 'all' && n.env !== environment) return false;

          if (status === 'all') return true;
          const statusValue = String(n.processingStatus || '').toLowerCase();
          const isProcessed = statusValue === 'processed' || statusValue === 'done' || statusValue === 'complete';
          if (status === 'processed') return isProcessed;
          if (status === 'unprocessed') return !isProcessed;
          return true;
        })
        .filter(n => {
          if (n.type !== 'signal') return true;
          const kind = (n.signalType || 'unknown') as keyof typeof visibleSignalKinds | 'unknown';
          if (kind === 'unknown') return true;
          return !!(visibleSignalKinds as any)[kind];
        });

      // Optional Story Focus: further restrict to a readable neighborhood.
      let storyFilteredNodes = activeNodes;
      if (storyFocusOn && storyFocusNode?.id) {
        const focusId = storyFocusNode.id;
        const preIds = new Set(storyFilteredNodes.map(n => n.id));
        const preById = new Map(storyFilteredNodes.map(n => [n.id, n] as const));

        const incident = edges
          .filter(e => preIds.has(e.source) && preIds.has(e.target))
          .filter(e => e.source === focusId || e.target === focusId);

        const allowed = new Set<string>();
        allowed.add(focusId);

        // Always keep directly-connected signal hubs.
        incident.forEach(e => {
          const otherId = e.source === focusId ? e.target : e.source;
          const other = preById.get(otherId);
          if (other?.type === 'signal') allowed.add(otherId);
        });

        // Rank memory neighbors by explainable edge types.
        const weight = (e: Edge): number => {
          const t = String(e.type || 'graph');
          const lbl = String((e as any).label || '');
          if (t === 'supersession') return 100;
          if (t === 'cohesion') {
            if (lbl === 'CO_TOPIC') return 95;
            if (lbl === 'CO_KNOWLEDGE_TYPE') return 85;
            if (lbl === 'CO_RING') return 75;
            return 70;
          }
          if (t === 'graph') return 60;
          if (t === 'semantic') return 50 + (typeof (e as any).similarity === 'number' ? (e as any).similarity : 0);
          return 40;
        };

        const candidates: Array<{ id: string; w: number }> = [];
        incident.forEach(e => {
          const otherId = e.source === focusId ? e.target : e.source;
          const other = preById.get(otherId);
          if (!other || other.type !== 'memory') return;
          candidates.push({ id: otherId, w: weight(e) });
        });

        candidates.sort((a, b) => b.w - a.w);
        const seen = new Set<string>();
        const top = candidates.filter(c => (seen.has(c.id) ? false : (seen.add(c.id), true))).slice(0, 18);
        top.forEach(t => allowed.add(t.id));

        // Also keep the signals of those top neighbors for context.
        const neighborIds = new Set(top.map(t => t.id));
        edges
          .filter(e => preIds.has(e.source) && preIds.has(e.target))
          .filter(e => (neighborIds.has(e.source) && preById.get(e.target)?.type === 'signal') || (neighborIds.has(e.target) && preById.get(e.source)?.type === 'signal'))
          .forEach(e => {
            allowed.add(e.source);
            allowed.add(e.target);
          });

        // Apply the restriction.
        storyFilteredNodes = storyFilteredNodes.filter(n => allowed.has(n.id));
      }

      activeNodes = storyFilteredNodes;

      const activeNodeIds = new Set(activeNodes.map(n => n.id));
      const nodeById = new Map(activeNodes.map(n => [n.id, n] as const));

      const activeEdges = edges
        .filter(e => activeNodeIds.has(e.source) && activeNodeIds.has(e.target))
        .filter(e => {
          if (e.type === 'semantic') {
            return !!showSemanticEdges;
          }
          if (e.type === 'cohesion') {
            return !!showCohesionEdges;
          }
          if (e.type === 'signal') {
            if (!visibleTypes.signal || !showSignalEdges) return false;
            const a = nodeById.get(e.source);
            const b = nodeById.get(e.target);
            const signalNode = a?.type === 'signal' ? a : (b?.type === 'signal' ? b : null);
            if (!signalNode) return true;
            const kind = (signalNode.signalType || 'unknown') as keyof typeof visibleSignalKinds | 'unknown';
            if (kind === 'unknown') return true;
            return !!(visibleSignalKinds as any)[kind];
          }
          if (e.type === 'cluster' || e.type === 'cluster_backbone') {
            return !!visibleTypes.cluster;
          }
          return true;
        });

      // Precompute adjacency weights for active focus mode.
      const adjacentNodes = new Set<string>();
      const adjacencyWeight = new Map<string, number>();
      const edgeWeightKey = (a: string, b: string) => (a < b ? `${a}::${b}` : `${b}::${a}`);
      const adjacencyEdgeWeight = new Map<string, number>();

      if (activeFocusNode) {
        const focusId = activeFocusNode.id;
        const focusImportance = clamp01(((activeFocusNode.importance ?? 5) as number) / 10);
        activeEdges.forEach(edge => {
          if (edge.source !== focusId && edge.target !== focusId) return;
          const otherId = edge.source === focusId ? edge.target : edge.source;
          adjacentNodes.add(otherId);

          const other = nodeById.get(otherId);
          const otherImportance = clamp01((((other?.importance ?? 5) as number) / 10));
          const base = edgeBaseStrength(edge);
          // Connection importance blends edge signal + node importance context.
          const w = clamp01(Math.max(base, 0.55 * otherImportance + 0.45 * focusImportance));

          const prev = adjacencyWeight.get(otherId) ?? 0;
          if (w > prev) adjacencyWeight.set(otherId, w);
          adjacencyEdgeWeight.set(edgeWeightKey(edge.source, edge.target), w);
        });
      }
      
      // Helper: Get label bounding box
      const getLabelBounds = (node: Node) => {
        ctx.font = '11px Inter, sans-serif';
        const metrics = ctx.measureText(node.label);
        return {
          x: node.x - metrics.width / 2 - 4,
          y: node.y + node.radius + 4,
          width: metrics.width + 8,
          height: 16
        };
      };
      
      // PHYSICS: Optimize repulsion for large graphs (skip distant pairs)
      const physicsNodes = activeNodes.length > 50 ? activeNodes.filter(n => n.type === 'memory') : activeNodes;
      for (let i = 0; i < physicsNodes.length; i++) {
        for (let j = i + 1; j < physicsNodes.length; j++) {
          const dx = physicsNodes[i].x - physicsNodes[j].x;
          const dy = physicsNodes[i].y - physicsNodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          
          // Skip if too far apart (performance)
          if (dist > 800) continue;
            const force = 1000 / (dist * dist); // Stronger inverse square
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            
            physicsNodes[i].vx += fx;
            physicsNodes[i].vy += fy;
            physicsNodes[j].vx -= fx;
            physicsNodes[j].vy -= fy;
          
          // Bounding Box Collision Detection (label-aware)
          const boundsA = getLabelBounds(physicsNodes[i]);
          const boundsB = getLabelBounds(physicsNodes[j]);
          
          // AABB collision check
          if (boundsA.x < boundsB.x + boundsB.width &&
              boundsA.x + boundsA.width > boundsB.x &&
              boundsA.y < boundsB.y + boundsB.height &&
              boundsA.y + boundsA.height > boundsB.y) {
            
            // Apply strong separation force
            const separationForce = 200 / (dist || 1);
            const fx = (dx / dist) * separationForce;
            const fy = (dy / dist) * separationForce;
            
            physicsNodes[i].vx += fx;
            physicsNodes[i].vy += fy;
            physicsNodes[j].vx -= fx;
            physicsNodes[j].vy -= fy;
          }
        }
      }
      
      // SPRINT 7: CEMENT PHYSICS - Loose springs
      activeEdges.forEach(edge => {
        const source = nodeById.get(edge.source);
        const target = nodeById.get(edge.target);
        
        if (source && target) {
          const dx = target.x - source.x;
          const dy = target.y - source.y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          
          // Loose springs (distance 150, strength 0.05)
          const restLength = 150;
          const springConstant = 0.05;
          
          const force = (dist - restLength) * springConstant;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          
          source.vx += fx;
          source.vy += fy;
          target.vx -= fx;
          target.vy -= fy;
        }
      });
      
      // SPRINT 23: DUAL PHYSICS - Gravity Ring for Orphans
      const cx = width / 2;
      const cy = height / 2;
      
      // Get connected IDs from edges
      const connectedIds = new Set<string>();
      activeEdges.forEach((edge: any) => {
        const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source;
        const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target;
        connectedIds.add(sourceId);
        connectedIds.add(targetId);
      });
      
      activeNodes.forEach(node => {
        const isOrphan = !connectedIds.has(node.id);
        
        if (isOrphan) {
          // OORT CLOUD PHYSICS: Scattered orbital bands
          const dx = node.x - cx;
          const dy = node.y - cy;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          
          // Deterministic randomness based on ID
          const hash = node.id.split('').reduce((a,b)=>a+b.charCodeAt(0),0);
          const orbitalBand = 400 + (hash % 200); // 400px to 600px
          
          // Pull towards target orbital band
          const radiusError = dist - orbitalBand;
          const pullStrength = 0.02; // Very gentle drift
          const fx = -(dx / dist) * radiusError * pullStrength;
          const fy = -(dy / dist) * radiusError * pullStrength;
          
          node.vx += fx;
          node.vy += fy;
        } else {
          // CONNECTED PHYSICS: Weak centering
          const dx = cx - node.x;
          const dy = cy - node.y;
          node.vx += dx * 0.001;
          node.vy += dy * 0.001;
        }
        
        // V1.6.2: RING GRAVITY - Keep memories in their ring zones (V5 mode)
        // V1.6.3: NEURAL WEB - Ring Gravity Disabled
        // We want nodes to find their own semantic clusters, not be forced into rings.
        /*
        if (viewMode === 'v5' && node.type === 'memory') {
          const ringRadii: Record<string, number> = {
            core: 50, domain: 180, topic: 300, leaf: 420
          };
          const ringZone = 60; // How far from target radius is OK
          const targetRadius = ringRadii[node.ring || 'leaf'] ?? 420;
          
          const dx = node.x - cx;
          const dy = node.y - cy;
          const currentDist = Math.sqrt(dx * dx + dy * dy) || 1;
          
          // Only apply force if outside zone
          const distError = currentDist - targetRadius;
          if (Math.abs(distError) > ringZone) {
            const pullStrength = 0.015; // Gentle radial force
            const fx = -(dx / currentDist) * distError * pullStrength;
            const fy = -(dy / currentDist) * distError * pullStrength;
            node.vx += fx;
            node.vy += fy;
          }
        }
        */
        
        // MUDDY SAND FRICTION: High viscosity, but allow some settling
        // 0.9 = Ice, 0.1 = Concrete. 0.4 = Mud.
        node.vx *= 0.4; 
        node.vy *= 0.4;
        
        // V3 LAYER GRAVITY: Pull memories to their Anchor (V3 only)
        if (viewMode === 'v3' && node.type === 'memory' && node.layer) {
             // Find corresponding anchor in the nodes array
             const anchorId = `v3_anchor_${node.layer}`;
             const anchor = nodes.find(n => n.id === anchorId);
             
             if (anchor) {
                 const dx = anchor.x - node.x;
                 const dy = anchor.y - node.y;
                 
                 // Strong pull (gravity)
                 // V28: TEMPORAL HEAT check? No, purely structural for now.
                 const strength = 0.02; // 2% pull per frame
                 node.vx += dx * strength;
                 node.vy += dy * strength;
             }
        }
        
        // Update position (unless dragging)
        if (draggingNode.current?.id !== node.id) {
          node.x += node.vx;
          node.y += node.vy;
        }

        // Physics lock for nodes with fx/fy (anchors, ring-layout nodes, orphans)
        const fxLock = (node as any).fx;
        const fyLock = (node as any).fy;
        if (draggingNode.current?.id !== node.id && fxLock != null && fyLock != null) {
          node.x = fxLock;
          node.y = fyLock;
          node.vx = 0;
          node.vy = 0;
        }
      });

      // 2. Render Step
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.translate(offset.current.x, offset.current.y);
      ctx.scale(scale.current, scale.current);

      // V1.6.3: NEURAL WEB - No Ring Guides
      // We are abandoning the solar system metaphor for a cleaner "brain" look.
      /*
      if (viewMode === 'v5') {
        const ringGuides = [
          { name: 'leaf', radius: 450, color: 'rgba(59, 130, 246, 0.06)', strokeColor: 'rgba(59, 130, 246, 0.15)', label: 'FACTS & PREFERENCES', sublabel: 'Individual memories - most changeable' },
          { name: 'topic', radius: 320, color: 'rgba(168, 85, 247, 0.08)', strokeColor: 'rgba(168, 85, 247, 0.2)', label: 'TOPICS', sublabel: 'Subject clusters' },
          { name: 'domain', radius: 200, color: 'rgba(6, 182, 212, 0.10)', strokeColor: 'rgba(6, 182, 212, 0.25)', label: 'DOMAINS', sublabel: 'Major life/work areas' },
          { name: 'core', radius: 80, color: 'rgba(245, 158, 11, 0.15)', strokeColor: 'rgba(245, 158, 11, 0.4)', label: 'CORE', sublabel: 'Your fundamental laws' },
        ];
        
        // Draw from outer to inner (so inner overlays)
        ringGuides.forEach((guide, idx) => {
          // Fill
          ctx.beginPath();
          ctx.arc(cx, cy, guide.radius, 0, Math.PI * 2);
          ctx.fillStyle = guide.color;
          ctx.fill();
          
          // Stroke (ring border)
          ctx.strokeStyle = guide.strokeColor;
          ctx.lineWidth = 1.5;
          ctx.setLineDash([8, 4]);
          ctx.stroke();
          ctx.setLineDash([]);
          
          // Ring label at top
          ctx.font = 'bold 11px Inter, sans-serif';
          ctx.fillStyle = guide.strokeColor;
          ctx.textAlign = 'center';
          ctx.fillText(guide.label, cx, cy - guide.radius + 18);
          
          // Sublabel (smaller, below main label)
          if (idx < 2) { // Only for outer rings where there's space
            ctx.font = '9px Inter, sans-serif';
            ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
            ctx.fillText(guide.sublabel, cx, cy - guide.radius + 30);
          }
        });
        
        // Center glow for CORE with stronger presence
        const coreGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, 120);
        coreGlow.addColorStop(0, 'rgba(245, 158, 11, 0.25)');
        coreGlow.addColorStop(0.5, 'rgba(245, 158, 11, 0.1)');
        coreGlow.addColorStop(1, 'rgba(245, 158, 11, 0)');
        ctx.beginPath();
        ctx.arc(cx, cy, 120, 0, Math.PI * 2);
        ctx.fillStyle = coreGlow;
        ctx.fill();
      }
      */

      const visibleNodes = activeNodes;
      const visibleEdges = activeEdges;
      
      // Draw Edges (with semantic/signal styling + bokeh focus)
      visibleEdges.forEach(edge => {
        const source = nodeById.get(edge.source);
        const target = nodeById.get(edge.target);
        if (!source || !target) return;
        
        const isConnected = activeFocusNode && (edge.source === activeFocusNode.id || edge.target === activeFocusNode.id);
        const isSemantic = edge.type === 'semantic';
        const isSignal = edge.type === 'signal';
        const isHovered = hoveredEdge?.source === edge.source && hoveredEdge?.target === edge.target;

        const w = isConnected
          ? (adjacencyEdgeWeight.get(edgeWeightKey(edge.source, edge.target)) ?? edgeBaseStrength(edge))
          : edgeBaseStrength(edge);

        const deemphasize = !!activeFocusNode && !isConnected;
        
        // ELECTRIC EDGES: Gradient + Pulse
        const gradient = ctx.createLinearGradient(source.x, source.y, target.x, target.y);
        gradient.addColorStop(0, source.color || '#94a3b8');
        gradient.addColorStop(1, target.color || '#94a3b8');
        
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        
        // Base Line (Sleek Gradient)
        ctx.strokeStyle = gradient;
        const baseWidth = isSemantic ? 2 : (isSignal ? 1 : 0.8);
        ctx.lineWidth = isConnected ? (baseWidth + 2.5 * w) : baseWidth;
        if (deemphasize) {
          ctx.globalAlpha = 0.05;
        } else if (isConnected) {
          ctx.globalAlpha = 0.25 + 0.65 * w;
        } else {
          ctx.globalAlpha = isSemantic ? 0.35 : 0.15;
        }
        ctx.stroke();
        
        // Electric Current Effect (Pulse Layer)
           if (isSemantic || isConnected) {
             const pulseFreq = isConnected ? 0.01 : 0.002;
             const phaseOffset = (edge.source.charCodeAt(0) + edge.target.charCodeAt(0)); 
             const pulse = (Math.sin(Date.now() * pulseFreq + phaseOffset) + 1) / 2; // 0 to 1
             
             ctx.strokeStyle = '#ffffff';
             ctx.lineWidth = isConnected ? (1.5 + 1.5 * w) : 1;
             ctx.globalAlpha = pulse * (isConnected ? (0.5 + 0.5 * w) : 0.2);
             ctx.stroke();
        }
        
        ctx.setLineDash([]); // Reset
        ctx.globalAlpha = 1.0; // Reset
        
        // SPRINT 14: Enhanced edge tooltip - Show WHY nodes are connected
        if (isHovered && isSemantic && edge.similarity) {
          const midX = (source.x + target.x) / 2;
          const midY = (source.y + target.y) / 2;
          
          // Build tooltip with context
          const similarity = (edge.similarity * 100).toFixed(0);
          const sourceLabel = source.short_label || source.label;
          const targetLabel = target.short_label || target.label;
          
          const lines = [
            `${similarity}% Similar`,
            `${sourceLabel} ↔ ${targetLabel}`
          ];
          
          ctx.font = '11px Inter, sans-serif';
          const maxWidth = Math.max(...lines.map(l => ctx.measureText(l).width));
          const padding = 8;
          const lineHeight = 16;
          const tooltipHeight = lines.length * lineHeight + padding * 2;
          
          // Tooltip background - AMBER with shadow
          ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
          ctx.shadowBlur = 8;
          ctx.fillStyle = 'rgba(245, 158, 11, 0.95)';
          ctx.fillRect(midX - maxWidth/2 - padding, midY - tooltipHeight/2,
                      maxWidth + padding*2, tooltipHeight);
          ctx.shadowBlur = 0;
          
          // Tooltip text
          ctx.fillStyle = '#fff';
          ctx.textAlign = 'center';
          lines.forEach((line, i) => {
            ctx.fillText(line, midX, midY - tooltipHeight/2 + padding + (i + 0.7) * lineHeight);
          });
        }
      });
      
      // Semantic Zoom: Determine which labels to show based on scale
      const getVisibleNodes = (currentScale: number, allNodes: Node[]) => {
        if (currentScale < 0.5) {
          // Far zoom: only high-degree entities
          return allNodes.filter(n => (n.type === 'entity' || n.type === 'signal') && (n.degree || 0) > 5);
        } else if (currentScale < 1.0) {
          // Medium zoom: entities and sessions
          return allNodes.filter(n => n.type !== 'memory');
        } else {
          // Close zoom: all nodes
          return allNodes;
        }
      };
      
      const visibleLabelNodes = getVisibleNodes(scale.current, nodes);
      const visibleLabelIds = new Set(visibleLabelNodes.map(n => n.id));
      
      // SPRINT 8: FUNCTIONAL SEARCH FILTER
      const matchesSearch = (node: Node) => {
        if (!searchTerm) return true; // Show all if no search term
        const term = searchTerm.toLowerCase();
        
        // Search EVERYTHING: Label, Content, Type
         const props = node.full_data?.parsed_props || node.full_data?.props || node.properties || node.full_data?.properties || {};
        return node.short_label?.toLowerCase().includes(term) ||
               node.label?.toLowerCase().includes(term) ||
               (props.content || '').toLowerCase().includes(term) ||
               (node.properties?.description || '').toLowerCase().includes(term) ||
               (props.topic || '').toLowerCase().includes(term) ||
           (props.summary || '').toLowerCase().includes(term) ||
           (node.signalValue || '').toLowerCase().includes(term);
      };
      
      // Update pulse phase ONCE per frame
      pulsePhase += PULSE_SPEED;

      // Draw Nodes with shape mapping
      visibleNodes.forEach(node => {
        // Focus mode dimming
        const isFocused = activeFocusNode?.id === node.id;
        const isAdjacent = !!activeFocusNode && adjacentNodes.has(node.id);
        const isDimmed = !!activeFocusNode && !isFocused && !isAdjacent;
        const isSearchMatch = matchesSearch(node);

        const connectionWeight = isAdjacent ? (adjacencyWeight.get(node.id) ?? 0.5) : 0;
        
        // DNA MAPPING: Use color from metadata (memory_type)
        let baseColor = node.color || '#10b981'; // Use DNA-mapped color or fallback to Emerald
        
        // V28: PULSE ANIMATION for critical memories OR Electric Effect
        const isCritical = (node.importance || 0) >= 9;
        const isElectric = isFocused || isAdjacent; // Electric Effect active?
        
        let pulseGlow = 0;
        if (isCritical || (focusedNode && isElectric)) {
          pulseGlow = Math.sin(pulsePhase) * 0.5 + 0.5; // 0 to 1 oscillation
        }
        
        // V28: TEMPORAL HEAT - Warmer colors for recent memories
        const createdAt = node.full_data?.created_at || node.properties?.created_at;
        const lastAccessed = node.full_data?.parsed_props?.last_accessed;
        const heat = createdAt ? calculateTemporalHeat(createdAt, lastAccessed) : 0.5;
        
        // SPRINT 8: Search-based opacity (ghost non-matches)
        let searchOpacity = 1.0;
        if (searchTerm && !isSearchMatch) {
          searchOpacity = 0.1; // Ghost mode for non-matches
        }
        
        // Apply opacity from DNA mapping (redundant status) + search filter
        const opacity = (node.opacity || 1.0) * searchOpacity;
        
        // Apply dimming or search highlighting with DNA opacity
        if (isSearchMatch && searchTerm) {
          ctx.fillStyle = '#fbbf24'; // Amber for search matches
          ctx.shadowColor = '#fbbf24';
          ctx.shadowBlur = 20;
          ctx.globalAlpha = 1.0;
        } else if (isDimmed) {
          // BOKEH MODE: heavy blur + very low alpha
          ctx.fillStyle = baseColor;
          ctx.shadowColor = baseColor;
          ctx.shadowBlur = 28;
          ctx.globalAlpha = 0.06 * opacity;
        } else if (isCritical || (focusedNode && isElectric)) {
          // V28: PULSE EFFECT for critical memories AND Electric Connections
          ctx.fillStyle = baseColor;
          ctx.shadowColor = baseColor;
          // Intense glow for Electric Effect
          const intensity = isElectric ? 40 : 25; 
          ctx.shadowBlur = 15 + (pulseGlow * intensity); 
          ctx.globalAlpha = 0.8 + (pulseGlow * 0.2); 
        } else {
          ctx.fillStyle = baseColor;
          ctx.shadowColor = baseColor;
          // V28: TEMPORAL HEAT affects glow intensity
          const focusBoost = isAdjacent ? (8 + 22 * connectionWeight) : 0;
          ctx.shadowBlur = isFocused ? 30 : (10 + heat * 10 + focusBoost);
          ctx.globalAlpha = opacity * (0.65 + heat * 0.25 + (isAdjacent ? (0.10 + 0.35 * connectionWeight) : 0));
        }
        
        // Draw shape based on node type
        ctx.save();
        ctx.translate(node.x, node.y);

        // Apply blur filter only to dimmed nodes (skip if too many for performance)
        const dimmedCount = visibleNodes.filter(n => {
          const isFoc = activeFocusNode?.id === n.id;
          const isAdj = !!activeFocusNode && adjacentNodes.has(n.id);
          return !!activeFocusNode && !isFoc && !isAdj;
        }).length;
        if (isDimmed && dimmedCount < 30) {
          ctx.filter = 'blur(3px)';
        }
        
        if (node.type === 'signal') {
          // Hexagon for signal hubs
          const r = node.radius;
          ctx.beginPath();
          for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 3) * i - Math.PI / 6;
            const px = Math.cos(a) * r;
            const py = Math.sin(a) * r;
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.closePath();
          ctx.fill();
        } else if (node.type === 'entity') {
          // Diamond shape for entities
          ctx.beginPath();
          ctx.moveTo(0, -node.radius);
          ctx.lineTo(node.radius, 0);
          ctx.lineTo(0, node.radius);
          ctx.lineTo(-node.radius, 0);
          ctx.closePath();
          ctx.fill();
        } else if (node.type === 'cluster') {
          // Small square for clusters
          const size = node.radius * 0.7;
          ctx.fillRect(-size, -size, size * 2, size * 2);
        } else if (node.type === 'session') {
          // Square shape for sessions
          const size = node.radius * 0.8;
          ctx.fillRect(-size, -size, size * 2, size * 2);
        } else {
          // Circle for memories
          ctx.beginPath();
          ctx.arc(0, 0, node.radius, 0, Math.PI * 2);
          ctx.fill();
        }

        // V1.6.3: STATUS & RECENCY INDICATORS
        if (!isDimmed) {
            // 1. Recency Ring (White Pulse for very recent items)
            if (heat > 0.9) {
                 ctx.beginPath();
                 ctx.arc(0, 0, node.radius + 4, 0, Math.PI * 2);
                 ctx.strokeStyle = `rgba(255, 255, 255, ${0.3 + Math.sin(pulsePhase * 2) * 0.2})`;
                 ctx.lineWidth = 2;
                 ctx.stroke();
            }
            
            // 2. Processing Status (Border)
            const pStatus = (node.processingStatus || '').toLowerCase();
            if (pStatus === 'processed') {
                 ctx.beginPath();
                 ctx.arc(0, 0, node.radius + 2, 0, Math.PI * 2);
                 ctx.strokeStyle = '#10B981'; // Emerald
                 ctx.lineWidth = 1.5;
                 ctx.stroke();
            } else if (pStatus === 'unprocessed' || pStatus === 'pending') {
                 ctx.beginPath();
                 ctx.arc(0, 0, node.radius + 2, 0, Math.PI * 2);
                 ctx.strokeStyle = '#F59E0B'; // Amber
                 ctx.lineWidth = 1.5;
                 ctx.setLineDash([3, 3]);
                 ctx.stroke();
                 ctx.setLineDash([]);
            }
        }
        
        ctx.restore();
        ctx.filter = 'none';
        ctx.shadowBlur = 0; // Reset shadow
        
        // Draw labels only for visible nodes (semantic zoom)
        if (!isDimmed && (visibleLabelIds.has(node.id) || isFocused || isSearchMatch)) {
          // SPRINT 7: Label sanitizer with pill background
          let displayLabel = node.label;
          if (displayLabel.startsWith('memory_')) {
            const desc = node.properties?.description || '';
            if (desc) {
              const words = desc.split(' ').slice(0, 3).join(' ');
              displayLabel = words.length > 20 ? words.substring(0, 20) + '...' : words;
            } else {
              displayLabel = 'Memory';
            }
          }
          // Strip "User" prefix
          displayLabel = displayLabel.replace(/^User /i, '');
          if (displayLabel.length > 15) {
            displayLabel = displayLabel.substring(0, 14) + '…';
          }
          
          // PILL BACKGROUND for readability
          ctx.font = '11px Inter, sans-serif';
          const textWidth = ctx.measureText(displayLabel).width;
          const padding = 4;
          const bgX = node.x - textWidth / 2 - padding;
          const bgY = node.y + node.radius + 8;
          const bgWidth = textWidth + padding * 2;
          const bgHeight = 16;
          
          // Draw rounded pill background (80% black)
          ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
          ctx.beginPath();
          ctx.roundRect(bgX, bgY, bgWidth, bgHeight, 4);
          ctx.fill();
          
          // Draw label text
          ctx.fillStyle = isDimmed ? '#94a3b8' : '#fff'; // Dimmed or white
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(displayLabel, node.x, bgY + bgHeight / 2);
        }
        
        // Hover effect - curated-first tooltip (no raw memory dump)
        if (hoveredNode?.id === node.id) {
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 2;
          ctx.stroke();

          const props =
            node.full_data?.parsed_props ||
            node.full_data?.props ||
            node.properties ||
            node.full_data?.properties ||
            {};

          const title = getCleanTitle(node);
          const summary =
            (props.summary || props.cognitive_analysis?.summary || '').toString().trim();

          const ring = (props.ring || node.ring || '').toString().trim();
          const topic = (props.topic || node.topic || '').toString().trim();
          const kt = (
            props.knowledge_type ||
            props.knowledgeType ||
            node.knowledgeType ||
            ''
          )
            .toString()
            .trim();

          const metaLine = [ring, topic, kt].filter(Boolean).join(' • ');

          // Connection counts in the CURRENT visible view (helps explain "isolated" feelings).
          const incident = visibleEdges.filter(
            (e: any) => e.source === node.id || e.target === node.id
          );
          const counts = incident.reduce(
            (acc: any, e: any) => {
              const t = String(e.type || 'graph');
              acc[t] = (acc[t] || 0) + 1;
              acc.total += 1;
              return acc;
            },
            { total: 0 }
          );

          const linesRaw: string[] = [];
          linesRaw.push(title);
          // Show summary for all nodes (memories have curated summaries, entities have descriptions)
          if (summary) {
            linesRaw.push(summary);
          }
          if (metaLine) linesRaw.push(metaLine);
          if (counts.total === 0) {
            linesRaw.push('Visible links: 0 (check toggles/filters)');
          } else {
            const signal = counts.signal || 0;
            const cohesion = counts.cohesion || 0;
            const graph = counts.graph || 0;
            linesRaw.push(
              `Visible links: ${counts.total} (signal ${signal}, cohesion ${cohesion}, graph ${graph})`
            );
          }

          const maxWidth = 360;
          const words = linesRaw
            .join('\n')
            .replace(/\s+/g, ' ')
            .trim()
            .split(' ');

          let lines: string[] = [];
          let currentLine = '';
          words.forEach((word: string) => {
            const testLine = currentLine + (currentLine ? ' ' : '') + word;
            const metrics = ctx.measureText(testLine);
            if (metrics.width > maxWidth && currentLine) {
              lines.push(currentLine);
              currentLine = word;
            } else {
              currentLine = testLine;
            }
          });
          if (currentLine) lines.push(currentLine);

          // Tooltip background
          const padding = 10;
          const lineHeight = 16;
          const tooltipHeight = lines.length * lineHeight + padding * 2;
          const tooltipWidth = maxWidth + padding * 2;
          const tooltipX = node.x - tooltipWidth / 2;
          const tooltipY = node.y - node.radius - tooltipHeight - 10;

          ctx.fillStyle = 'rgba(30, 41, 59, 0.95)';
          ctx.fillRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);
          ctx.strokeStyle = '#10b981';
          ctx.lineWidth = 1;
          ctx.strokeRect(tooltipX, tooltipY, tooltipWidth, tooltipHeight);

          // Tooltip text
          ctx.fillStyle = '#fff';
          ctx.font = '12px Inter, sans-serif';
          ctx.textAlign = 'left';
          lines.forEach((line, i) => {
            ctx.fillText(line, tooltipX + padding, tooltipY + padding + i * lineHeight + 12);
          });

          ctx.textAlign = 'center'; // Reset
        }
      });
      
      ctx.restore();
      requestRef.current = requestAnimationFrame(animate);
    };
    
    requestRef.current = requestAnimationFrame(animate);
    
    return () => {
      if (requestRef.current) cancelAnimationFrame(requestRef.current);
    };
  }, [data]); // Re-bind when data changes (positions are ref-stable)

  // Resize Handler
  useEffect(() => {
    const handleResize = () => {
      if (canvasRef.current) {
        canvasRef.current.width = window.innerWidth;
        canvasRef.current.height = window.innerHeight;
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Mouse Handlers
  const isNodeVisibleNow = (node: Node) => {
    const visibleTypes = visibleTypesRef.current;
    const environment = environmentRef.current;
    const status = statusRef.current;
    const visibleSignalKinds = visibleSignalKindsRef.current;

    if (!visibleTypes[node.type as keyof typeof visibleTypes]) return false;

    if (node.type === 'memory') {
      if (environment !== 'all' && node.env !== environment) return false;
      if (status === 'all') return true;
      const statusValue = String(node.processingStatus || '').toLowerCase();
      const isProcessed = statusValue === 'processed' || statusValue === 'done' || statusValue === 'complete';
      if (status === 'processed') return isProcessed;
      if (status === 'unprocessed') return !isProcessed;
    }

    if (node.type === 'signal') {
      const kind = (node.signalType || 'unknown') as keyof typeof visibleSignalKinds | 'unknown';
      if (kind !== 'unknown' && !(visibleSignalKinds as any)[kind]) return false;
    }

    return true;
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = (e.clientX - rect.left - offset.current.x) / scale.current;
    const y = (e.clientY - rect.top - offset.current.y) / scale.current;
    
    // Check node hit
    const hitNode = nodesRef.current.filter(isNodeVisibleNow).find(n => {
      const dx = n.x - x;
      const dy = n.y - y;
      return Math.sqrt(dx*dx + dy*dy) < n.radius + 5;
    });
    
    if (hitNode) {
      draggingNode.current = hitNode;
      // Click to focus (toggle)
      if (e.shiftKey) {
        setFocusedNode(focusedNode?.id === hitNode.id ? null : hitNode);
      } else {
        // Regular click opens inspector
        setSelectedNode(hitNode);
      }
    } else {
      isDraggingCanvas.current = true;
      lastMousePos.current = { x: e.clientX, y: e.clientY };
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = (e.clientX - rect.left - offset.current.x) / scale.current;
    const y = (e.clientY - rect.top - offset.current.y) / scale.current;
    
    // Hover check for nodes
    const hitNode = nodesRef.current.filter(isNodeVisibleNow).find(n => {
        const dx = n.x - x;
        const dy = n.y - y;
        return Math.sqrt(dx*dx + dy*dy) < n.radius + 5;
    });
    setHoveredNode(hitNode || null);
    
    // Hover check for edges (semantic edges only)
    let hitEdge: Edge | null = null;
    const edges = edgesRef.current;
    const nodes = nodesRef.current;
    
    for (const edge of edges) {
      if (edge.type !== 'semantic') continue;
      
      const source = nodes.find(n => n.id === edge.source);
      const target = nodes.find(n => n.id === edge.target);
      if (!source || !target) continue;
      
      // Check if mouse is near edge line (within 10px)
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const length = Math.sqrt(dx*dx + dy*dy);
      
      // Project mouse point onto line
      const t = Math.max(0, Math.min(1, ((x - source.x) * dx + (y - source.y) * dy) / (length * length)));
      const projX = source.x + t * dx;
      const projY = source.y + t * dy;
      
      const dist = Math.sqrt((x - projX)**2 + (y - projY)**2);
      if (dist < 10) {
        hitEdge = edge;
        break;
      }
    }
    setHoveredEdge(hitEdge);
    
    if (draggingNode.current) {
      draggingNode.current.x = x;
      draggingNode.current.y = y;
      // If this node is fx/fy locked (ring layout / anchors), drag should move the lock.
      const fxLock = (draggingNode.current as any).fx;
      const fyLock = (draggingNode.current as any).fy;
      if (fxLock != null && fyLock != null) {
        (draggingNode.current as any).fx = x;
        (draggingNode.current as any).fy = y;
      }
      draggingNode.current.vx = 0;
      draggingNode.current.vy = 0;
    } else if (isDraggingCanvas.current) {
      const dx = e.clientX - lastMousePos.current.x;
      const dy = e.clientY - lastMousePos.current.y;
      offset.current.x += dx;
      offset.current.y += dy;
      lastMousePos.current = { x: e.clientX, y: e.clientY };
    }
  };

  const handleMouseUp = () => {
    draggingNode.current = null;
    isDraggingCanvas.current = false;
  };
  
  const handleWheel = (e: React.WheelEvent) => {
      const zoomSensitivity = 0.001;
      const newScale = scale.current - e.deltaY * zoomSensitivity;
      scale.current = Math.max(0.1, Math.min(5, newScale));
  };

  return (
    <div className="relative w-full h-full">
      {/* Controls Drawer Toggle */}
      <div className="absolute top-20 left-4 z-50 pointer-events-auto">
        <button
          className="flex items-center gap-2 px-3 py-2 bg-slate-900/90 backdrop-blur rounded-lg border border-slate-700 hover:border-cyan-500/60 text-slate-200 shadow-lg transition-colors"
          onClick={() => setControlsOpen(v => !v)}
        >
          <SlidersHorizontal size={16} />
          <span className="text-sm font-medium">Controls</span>
          <span className="text-[11px] text-slate-400">{controlsOpen ? 'Hide' : 'Show'}</span>
        </button>
      </div>

      {/* Controls Drawer */}
      {controlsOpen && (
        <div className="absolute top-20 left-4 z-50 w-[340px] max-h-[75vh] overflow-auto bg-slate-900/95 backdrop-blur rounded-xl border border-slate-700 shadow-2xl pointer-events-auto">
          <div className="sticky top-0 bg-slate-900/95 backdrop-blur border-b border-slate-800 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-200">
              <SlidersHorizontal size={16} />
              <div className="text-sm font-semibold">Controls</div>
            </div>
            <button
              className="p-2 rounded-lg hover:bg-slate-800 text-slate-300 hover:text-white transition-colors"
              onClick={() => setControlsOpen(false)}
              aria-label="Close controls"
            >
              <X size={16} />
            </button>
          </div>

          <div className="p-4 space-y-4">
            {/* Node Type Toggles */}
            <div>
              <div className="text-xs font-bold mb-2 text-slate-300 uppercase tracking-wide">Node Types</div>
              <div className="space-y-1">
                {(Object.keys(visibleTypes) as Array<keyof typeof visibleTypes>).map((type) => (
                  <label key={type} className="flex items-center gap-2 cursor-pointer text-slate-300">
                    <input
                      type="checkbox"
                      checked={visibleTypes[type]}
                      onChange={() => setVisibleTypes(prev => ({...prev, [type]: !prev[type]}))}
                    />
                    <span className="capitalize">{type}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Signal Controls */}
            {visibleTypes.signal && (
              <div className="pt-3 border-t border-slate-800">
                <div className="text-xs font-bold mb-2 text-slate-300 uppercase tracking-wide">Signals</div>

                <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                  <input
                    type="checkbox"
                    checked={showSignalEdges}
                    onChange={() => setShowSignalEdges(v => !v)}
                  />
                  <span>Show signal edges</span>
                </label>

                <div className="mt-2 space-y-1">
                  <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                    <input
                      type="checkbox"
                      checked={visibleSignalKinds.topic}
                      onChange={() => setVisibleSignalKinds(prev => ({ ...prev, topic: !prev.topic }))}
                    />
                    <span className="text-cyan-300">Topic hubs</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                    <input
                      type="checkbox"
                      checked={visibleSignalKinds.knowledge_type}
                      onChange={() => setVisibleSignalKinds(prev => ({ ...prev, knowledge_type: !prev.knowledge_type }))}
                    />
                    <span className="text-purple-300">Knowledge-type hubs</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                    <input
                      type="checkbox"
                      checked={visibleSignalKinds.ring}
                      onChange={() => setVisibleSignalKinds(prev => ({ ...prev, ring: !prev.ring }))}
                    />
                    <span className="text-amber-300">Ring hubs</span>
                  </label>
                </div>
              </div>
            )}

            {/* Edge Controls */}
            <div className="pt-3 border-t border-slate-800">
              <div className="text-xs font-bold mb-2 text-slate-300 uppercase tracking-wide">Edges</div>

              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="checkbox"
                  checked={showCohesionEdges}
                  onChange={() => setShowCohesionEdges(v => !v)}
                />
                <span>Show cohesion edges</span>
                <span className="text-[10px] text-slate-500">(shared signals)</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer text-slate-300 mt-2">
                <input
                  type="checkbox"
                  checked={showSemanticEdges}
                  onChange={() => setShowSemanticEdges(v => !v)}
                />
                <span>Show semantic edges</span>
                <span className="text-[10px] text-slate-500">(subjective)</span>
              </label>

              {!showSemanticEdges && (
                <div className="mt-2 text-[11px] text-slate-500">
                  Semantic edges are hidden by default to keep connectivity explainable.
                </div>
              )}
            </div>

            {/* View Mode Toggle */}
            <div className="pt-3 border-t border-slate-800">
              <div className="text-xs font-bold mb-2 text-slate-300 uppercase tracking-wide">View Mode</div>
              <label className="flex items-center gap-2 cursor-pointer text-slate-300">
                <input
                  type="radio"
                  name="viewMode"
                  checked={viewMode === 'v3'}
                  onChange={() => setViewMode('v3')}
                />
                <span>V3 (layer/sublayer)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer text-slate-300 mt-1">
                <input
                  type="radio"
                  name="viewMode"
                  checked={viewMode === 'v5'}
                  onChange={() => setViewMode('v5')}
                />
                <span>V5 (ring/topic)</span>
              </label>
            </div>

            {/* Legend */}
            <div className="pt-3 border-t border-slate-800">
              <div className="text-xs font-bold mb-2 text-slate-300 uppercase tracking-wide">Legend</div>
              {viewMode === 'v3' ? (
                <div className="space-y-1 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="text-red-400">🔴 SELF</span>
                    <span className="text-slate-400">identity • preference • constraint</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-blue-400">🔵 WORLD</span>
                    <span className="text-slate-400">fact • failure • method</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-200">⚪ INTENT</span>
                    <span className="text-slate-400">rule • goal • anti-pattern</span>
                  </div>
                  <div className="mt-2 text-[10px] text-slate-500">Node size = Importance (1–10)</div>
                </div>
              ) : (
                <div className="space-y-1 text-[11px]">
                  <div className="flex items-center justify-between">
                    <span className="text-amber-400">CORE</span>
                    <span className="text-slate-400">Your fundamental laws & beliefs</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-cyan-400">DOMAIN</span>
                    <span className="text-slate-400">Major life/work areas</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-purple-400">TOPIC</span>
                    <span className="text-slate-400">Subject clusters</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-blue-400">LEAF</span>
                    <span className="text-slate-400">Individual facts & preferences</span>
                  </div>
                  <div className="mt-2 pt-2 border-t border-slate-800">
                    <div className="text-[10px] text-slate-500">
                      Center = most stable. Outer = most changeable.
                    </div>
                    <div className="mt-1 text-[10px] text-slate-500">Node size = Importance (1-10)</div>
                  </div>
                </div>
              )}
            </div>

            {/* Help */}
            <div className="pt-3 border-t border-slate-800">
              <div className="flex items-center gap-2 text-xs font-bold mb-2 text-slate-300 uppercase tracking-wide">
                <HelpCircle size={14} /> Help
              </div>
              <div className="text-[11px] text-slate-300 space-y-1">
                <div><span className="text-slate-200 font-semibold">Click</span> inspect node</div>
                <div><span className="text-slate-200 font-semibold">Shift+Click</span> focus mode</div>
                <div><span className="text-slate-200 font-semibold">Drag</span> move nodes / pan canvas</div>
                <div><span className="text-slate-200 font-semibold">Scroll</span> zoom</div>
                <div><span className="text-slate-200 font-semibold">Esc</span> clear focus/search</div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="absolute top-20 right-4 bg-slate-900/90 p-3 rounded-lg border border-slate-700 text-xs z-50 pointer-events-none">
        <div className="text-slate-400 font-bold mb-2">OVERVIEW</div>
        <div className="text-emerald-400">{graphStats.memories} memories</div>
        <div className="text-cyan-400">{graphStats.signalCoverage}% classified</div>
        <div className="text-blue-400">{graphStats.avgConnections} avg links</div>
        <div className="text-slate-400 mt-1">{graphStats.visibleEdges} visible edges</div>
      </div>

      {/* V1.6.2: KNOWLEDGE MAP GUIDE - Bottom left explanation */}
      {viewMode === 'v5' && !selectedNode && (
        <div className="absolute bottom-20 left-4 bg-slate-900/95 p-4 rounded-lg border border-slate-700 text-xs z-50 max-w-xs pointer-events-none">
          <div className="text-amber-400 font-bold mb-2 text-sm">YOUR KNOWLEDGE MAP</div>
          <div className="space-y-2 text-slate-300">
            <div className="flex items-start gap-2">
              <span className="text-amber-400 font-bold">Center:</span>
              <span>Your core beliefs and laws - the foundation of who you are</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-cyan-400 font-bold">Inner:</span>
              <span>Major domains of your life and work</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-purple-400 font-bold">Middle:</span>
              <span>Topic clusters - specific subject areas</span>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-blue-400 font-bold">Outer:</span>
              <span>Individual facts and preferences - the details</span>
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-700 text-slate-400">
            Click any node to explore. Closer to center = more fundamental.
          </div>
        </div>
      )}

      {/* Story Focus Badge */}
      {storyFocusOn && storyFocusNode && (
        <div className="absolute top-36 right-4 z-50 pointer-events-auto">
          <div className="flex items-center gap-2 bg-slate-900/90 backdrop-blur px-3 py-2 rounded-lg border border-cyan-500/30 shadow-lg">
            <div className="text-xs font-bold text-cyan-300 uppercase tracking-wider">Story Focus</div>
            <div className="text-xs text-slate-300">
              ON • {graphStats.visibleNodes} nodes • {graphStats.memories} memories
            </div>
            <div className="text-[11px] text-slate-500 truncate max-w-[160px]">
              {String(storyFocusNode.label || storyFocusNode.short_label || storyFocusNode.originalLabel || '')}
            </div>
            <button
              className="ml-2 px-2 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
              onClick={() => {
                setStoryFocusOn(false);
                setStoryFocusNode(null);
              }}
            >
              Clear
            </button>
          </div>
        </div>
      )}
      
      {/* V28: COGNITIVE MIRROR SIDEBAR - Enhanced Inspector */}
      {selectedNode && (() => {
        // Helper: Get prop from n.properties (API) first, then n.full_data.parsed_props (legacy)
        const getProp = (key: string, fallback: any = null) => {
          const props = selectedNode.properties as Record<string, any> | undefined;
          return props?.[key] 
              ?? selectedNode.full_data?.parsed_props?.[key] 
              ?? fallback;
        };

        if (selectedNode.type === 'signal') {
          const signalType = selectedNode.signalType || getProp('signal_type', 'unknown');
          const signalValue = selectedNode.signalValue || getProp('value', '');
          return (
            <div className="fixed right-0 top-0 h-full w-[420px] bg-gradient-to-b from-slate-900 to-slate-950 border-l border-cyan-500/30 shadow-2xl overflow-y-auto z-50">
              <div className="bg-gradient-to-r from-cyan-500/20 via-purple-500/20 to-amber-500/20 p-6 border-b border-slate-700/50">
                <button onClick={() => setSelectedNode(null)} className="absolute top-4 right-4 p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-white transition-colors">
                  <span className="text-lg">✕</span>
                </button>

                <div className="flex items-start gap-3 mt-2">
                  <div className="p-3 rounded-xl bg-slate-800/50 text-slate-200 border border-slate-700">
                    ⬡
                  </div>
                  <div className="flex-1">
                    <h2 className="text-xl font-bold text-white leading-tight">
                      {selectedNode.short_label || selectedNode.label}
                    </h2>
                    <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider">
                      SIGNAL HUB • {String(signalType).toUpperCase()} {signalValue ? `• ${String(signalValue)}` : ''}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 mt-4">
                  <div className="flex-1">
                    <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                      <span>CONNECTED MEMORIES</span>
                      <span className="font-mono">{selectedNode.degree || 0}</span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-purple-500" style={{ width: '100%' }} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-6 space-y-4">
                <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-700/50">
                  <div className="text-[10px] text-slate-500 uppercase">Signal Type</div>
                  <div className="text-sm text-slate-200 font-bold">{String(signalType)}</div>
                  {signalValue && (
                    <>
                      <div className="mt-3 text-[10px] text-slate-500 uppercase">Value</div>
                      <div className="text-sm text-slate-200 break-words">{String(signalValue)}</div>
                    </>
                  )}
                </div>

                <div className="pt-2 border-t border-slate-800">
                  <h3 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase mb-3">
                    <span>⚡</span> Quick Actions
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      className="p-2 bg-slate-500/10 hover:bg-slate-500/20 text-slate-200 rounded-lg text-xs font-medium transition-colors border border-slate-500/30"
                      onClick={() => setFocusedNode(selectedNode)}
                    >
                      🎯 Focus Hub
                    </button>
                    <button
                      className="p-2 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 rounded-lg text-xs font-medium transition-colors border border-amber-500/30"
                      onClick={() => {
                        if (signalValue && onSearchTermChange) onSearchTermChange(String(signalValue));
                      }}
                    >
                      🔎 Search Value
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        }
        
        return (
        <div className="fixed right-0 top-0 h-full w-[420px] bg-gradient-to-b from-slate-900 to-slate-950 border-l border-cyan-500/30 shadow-2xl overflow-y-auto z-50">
          
          {/* Gradient Header */}
          <div className="bg-gradient-to-r from-cyan-500/20 via-purple-500/20 to-pink-500/20 p-6 border-b border-slate-700/50">
            {/* Close Button */}
            <button onClick={() => setSelectedNode(null)} className="absolute top-4 right-4 p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-white transition-colors">
              <span className="text-lg">✕</span>
            </button>

            {/* Title with Memory Type Icon */}
            <div className="flex items-start gap-3 mt-2">
              <div className={`p-3 rounded-xl ${
                getProp('memory_type') === 'decision' ? 'bg-red-500/20 text-red-400' :
                getProp('memory_type') === 'insight' ? 'bg-purple-500/20 text-purple-400' :
                getProp('memory_type') === 'preference' ? 'bg-yellow-500/20 text-yellow-400' :
                getProp('memory_type') === 'episodic' ? 'bg-emerald-500/20 text-emerald-400' :
                'bg-blue-500/20 text-blue-400'
              }`}>
                {getProp('memory_type') === 'decision' ? '⚖️' :
                 getProp('memory_type') === 'insight' ? '💡' :
                 getProp('memory_type') === 'preference' ? '⭐' :
                 getProp('memory_type') === 'episodic' ? '📝' :
                 '📚'}
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-bold text-white leading-tight">
                  {getCleanTitle(selectedNode)}
                </h2>
                <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider">
                  {viewMode === 'v5'
                    ? `${String(getProp('ring', 'leaf')).toUpperCase()} • ${String(getProp('knowledge_type', getProp('memory_type', 'unknown')))}${getProp('topic') ? ` • ${String(getProp('topic'))}` : ''}`
                    : `${String(getProp('layer', 'WORLD')).toUpperCase()}.${String(getProp('sublayer', 'fact'))} • ${String(getProp('memory_type', 'fact'))}`
                  }
                </p>
              </div>
            </div>
            
            {/* Importance & Heat Indicators */}
            <div className="flex items-center gap-3 mt-4">
              {/* Importance Bar */}
              <div className="flex-1">
                <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                  <span>IMPORTANCE</span>
                  <span className="font-mono">{getProp('importance', 5)}/10</span>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full transition-all ${
                      getProp('importance', 5) >= 9 ? 'bg-gradient-to-r from-red-500 to-orange-500 animate-pulse' :
                      getProp('importance', 5) >= 7 ? 'bg-gradient-to-r from-yellow-500 to-amber-500' :
                      'bg-gradient-to-r from-cyan-500 to-blue-500'
                    }`}
                    style={{ width: `${getProp('importance', 5) * 10}%` }}
                  />
                </div>
              </div>
              
              {/* Status Badge */}
              <span className={`px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                getProp('status') === 'verified' ? 'bg-emerald-500/20 text-emerald-400' :
                getProp('status') === 'contradictory' ? 'bg-red-500/20 text-red-400' :
                'bg-slate-700/50 text-slate-300'
              }`}>
                {getProp('status', 'Active')}
              </span>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* CURATED VIEW - What This Memory Means */}
            {(() => {
              const strategicInsight =
                selectedNode.full_data?.parsed_props?.cognitive_analysis?.strategic_insight ||
                getProp('strategic_insight') ||
                getProp('insight') ||
                '';
              const rawContent = String(getProp('content') || selectedNode.full_data?.description || '').trim();
              const summary =
                selectedNode.full_data?.parsed_props?.cognitive_analysis?.summary ||
                getProp('summary') ||
                (rawContent ? (rawContent.length > 220 ? rawContent.slice(0, 220).trim() + '…' : rawContent) : '') ||
                '';

              if (!strategicInsight && !summary) return null;

              return (
                <div className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 p-4 rounded-xl border border-cyan-500/20">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-cyan-300">🧭</span>
                    <h4 className="text-xs text-cyan-300 uppercase font-bold tracking-wider">Curated Understanding</h4>
                  </div>

                  {summary && (
                    <div className="mb-3">
                      <div className="text-[10px] text-slate-400 uppercase tracking-wider font-bold">Summary</div>
                      <div className="text-sm text-slate-200 leading-relaxed">{String(summary)}</div>
                    </div>
                  )}

                  {strategicInsight && (
                    <div>
                      <div className="text-[10px] text-purple-300 uppercase tracking-wider font-bold">Actionable Insight</div>
                      <div className="text-sm text-slate-200 leading-relaxed">{String(strategicInsight)}</div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* RAW MEMORY - Collapsed by default */}
            <details className="border border-slate-800 rounded-xl overflow-hidden">
              <summary className="px-4 py-3 bg-slate-900/60 cursor-pointer text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <span className="text-slate-400">📄</span> Raw Memory
                <span className="text-[10px] text-slate-500 font-normal">(click to expand)</span>
              </summary>
              <div className="p-4 bg-slate-800/30">
                <pre className="whitespace-pre-wrap text-slate-300 text-sm leading-relaxed font-sans">
                  {String(getProp('content') || selectedNode.full_data?.description || 'No content available')}
                </pre>
              </div>
            </details>

            {/* WHY CONNECTED - Explainable context */}
            {(() => {
              const edges = edgesRef.current || [];
              const nodes = nodesRef.current || [];
              const nodeById = new Map(nodes.map((n: any) => [n.id, n] as const));
              const id = selectedNode.id;

              const incident = edges.filter((e: any) => e.source === id || e.target === id);
              const signals = incident
                .map((e: any) => {
                  const otherId = e.source === id ? e.target : e.source;
                  const other = nodeById.get(otherId);
                  if (!other || other.type !== 'signal') return null;
                  const kind = other.signalType || other.full_data?.properties?.signal_type || other.properties?.signal_type || 'signal';
                  const value = other.signalValue || other.full_data?.properties?.value || other.properties?.value || other.label || other.short_label || '';
                  return { kind: String(kind), value: String(value), id: otherId };
                })
                .filter(Boolean) as Array<{ kind: string; value: string; id: string }>;

              const neighbors = incident
                .map((e: any) => {
                  const otherId = e.source === id ? e.target : e.source;
                  const other = nodeById.get(otherId);
                  if (!other || otherId === id) return null;
                  return {
                    otherId,
                    other,
                    type: String(e.type || 'graph'),
                    label: String(e.label || 'RELATED'),
                    similarity: typeof e.similarity === 'number' ? e.similarity : undefined,
                  };
                })
                .filter(Boolean) as Array<any>;

              const score = (n: any) => {
                if (n.type === 'supersession') return 10;
                if (n.type === 'signal') return 8;
                if (n.type === 'cohesion') return 7;
                if (n.type === 'graph') return 6;
                if (n.type === 'semantic') return 5 + (n.similarity ?? 0);
                return 4;
              };

              const topNeighbors = neighbors
                .filter(n => n.other?.type !== 'signal')
                .sort((a, b) => score(b) - score(a))
                .slice(0, 6);

              if (signals.length === 0 && topNeighbors.length === 0) return null;

              return (
                <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-emerald-400">🧩</span>
                    <h4 className="text-xs text-emerald-400 uppercase font-bold tracking-wider">Why This Is Connected</h4>
                  </div>

                  {signals.length > 0 && (
                    <div className="mb-4">
                      <div className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mb-2">Signals</div>
                      <div className="flex flex-wrap gap-2">
                        {signals.slice(0, 12).map((s, i) => (
                          <span key={`${s.id}-${i}`} className="px-2 py-1 bg-slate-800 text-slate-200 text-xs rounded-full border border-slate-700">
                            <span className="text-slate-400">{s.kind}:</span> {s.value}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {topNeighbors.length > 0 && (
                    <div>
                      <div className="text-[10px] text-slate-500 uppercase tracking-wider font-bold mb-2">Strongest Neighbors</div>
                      <div className="space-y-2">
                        {topNeighbors.map((n, i) => (
                          <div key={`${n.otherId}-${i}`} className="flex items-start justify-between gap-3 bg-slate-800/30 border border-slate-800 rounded-lg px-3 py-2">
                            <div className="min-w-0">
                              <div className="text-sm text-slate-200 truncate">{String(n.other?.label || n.other?.short_label || n.other?.originalLabel || n.other?.id)}</div>
                              <div className="text-[10px] text-slate-500 uppercase tracking-wider">
                                {n.type} • {n.label}{typeof n.similarity === 'number' ? ` • sim ${n.similarity.toFixed(2)}` : ''}
                              </div>
                            </div>
                            <button
                              className="text-[11px] text-cyan-300 hover:text-cyan-200"
                              onClick={() => {
                                const target = nodeById.get(n.otherId);
                                if (target) setSelectedNode(target);
                              }}
                            >
                              Inspect
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* METADATA GRID - Second Brain Metrics */}
            <div>
              <h3 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase mb-3">
                <span>🧠</span> Second Brain Metrics
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Layer</div>
                  <div className="text-sm text-slate-300 uppercase font-bold">
                    {getProp('layer', 'world')}.{getProp('sublayer', 'fact')}
                  </div>
                </div>
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Recalls</div>
                  <div className="text-sm text-slate-300 font-mono">
                    {getProp('access_count', 0)}× used
                  </div>
                </div>
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Created</div>
                  <div className="text-sm text-slate-300 font-mono">
                    {selectedNode.full_data?.created_at ? new Date(selectedNode.full_data.created_at).toLocaleDateString() : 'N/A'}
                  </div>
                </div>
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Domain</div>
                  <div className="text-sm text-slate-300 capitalize">
                    {getProp('domain', 'General')}
                  </div>
                </div>
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Connections</div>
                  <div className="text-sm text-slate-300 font-mono">
                    {selectedNode.degree || 0} links
                  </div>
                </div>
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Type</div>
                  <div className="text-sm text-slate-300 capitalize">
                    {getProp('memory_type', 'fact')}
                  </div>
                </div>
              </div>
            </div>

            {/* TAGS */}
            {getProp('tags') && (
              <div>
                <h3 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase mb-3">
                  <span>🏷️</span> Tags
                </h3>
                <div className="flex flex-wrap gap-2">
                  {(typeof getProp('tags') === 'string' 
                    ? getProp('tags').split(',') 
                    : getProp('tags')
                  ).map((tag: string, i: number) => (
                    <span key={i} className="px-2 py-1 bg-slate-800 text-cyan-400 text-xs rounded-full border border-cyan-500/30">
                      {tag.trim()}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* v1.6.2: COGNITIVE FIELDS - Concepts, Surfaces When, Authority Score */}
            {(() => {
              // Parse cognitive fields from snapshot data
              const conceptsRaw = getProp('concepts');
              const surfacesWhenRaw = getProp('surfaces_when');
              const authorityScoreRaw = getProp('authority_score');

              // Safe JSON parse for array fields (stored as JSON strings in ChromaDB)
              const parseJsonArray = (raw: any): string[] => {
                if (!raw) return [];
                if (Array.isArray(raw)) return raw.map(String);
                if (typeof raw === 'string') {
                  try {
                    const parsed = JSON.parse(raw);
                    if (Array.isArray(parsed)) return parsed.map(String);
                  } catch {
                    // Not JSON, try comma-separated
                    if (raw.includes(',')) return raw.split(',').map((s: string) => s.trim()).filter(Boolean);
                  }
                }
                return [];
              };

              const concepts = parseJsonArray(conceptsRaw);
              const surfacesWhen = parseJsonArray(surfacesWhenRaw);
              const authorityScore = typeof authorityScoreRaw === 'number' 
                ? authorityScoreRaw 
                : parseFloat(String(authorityScoreRaw || '0')) || 0;

              const hasCognitiveData = concepts.length > 0 || surfacesWhen.length > 0 || authorityScore > 0;

              if (!hasCognitiveData) return null;

              return (
                <div className="bg-gradient-to-r from-purple-500/10 to-cyan-500/10 p-4 rounded-xl border border-purple-500/20">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-purple-300">🧬</span>
                    <h4 className="text-xs text-purple-300 uppercase font-bold tracking-wider">Cognitive Fields</h4>
                    <span className="text-[9px] text-slate-500 ml-auto">v1.6.2</span>
                  </div>

                  {/* CONCEPTS */}
                  {concepts.length > 0 && (
                    <div className="mb-3">
                      <div className="text-[10px] text-slate-400 uppercase tracking-wider font-bold mb-2">🎯 Concepts</div>
                      <div className="flex flex-wrap gap-1.5">
                        {concepts.slice(0, 10).map((concept: string, i: number) => (
                          <span 
                            key={i} 
                            className="px-2 py-0.5 bg-cyan-500/20 text-cyan-300 text-[11px] rounded-full border border-cyan-500/30 cursor-pointer hover:bg-cyan-500/30 transition-colors"
                            onClick={() => onSearchTermChange?.(concept)}
                            title={`Search for "${concept}"`}
                          >
                            {concept}
                          </span>
                        ))}
                        {concepts.length > 10 && (
                          <span className="text-[10px] text-slate-500">+{concepts.length - 10} more</span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* SURFACES WHEN */}
                  {surfacesWhen.length > 0 && (
                    <div className="mb-3">
                      <div className="text-[10px] text-slate-400 uppercase tracking-wider font-bold mb-2">⚡ Surfaces When</div>
                      <div className="space-y-1">
                        {surfacesWhen.slice(0, 5).map((trigger: string, i: number) => (
                          <div 
                            key={i} 
                            className="text-[11px] text-slate-300 pl-3 border-l-2 border-purple-500/40"
                          >
                            {trigger}
                          </div>
                        ))}
                        {surfacesWhen.length > 5 && (
                          <div className="text-[10px] text-slate-500 pl-3">+{surfacesWhen.length - 5} more triggers</div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* AUTHORITY SCORE */}
                  {authorityScore > 0 && (
                    <div>
                      <div className="flex justify-between text-[10px] mb-1">
                        <span className="text-slate-400 uppercase tracking-wider font-bold">📊 Authority Score</span>
                        <span className="font-mono text-slate-300">{authorityScore.toFixed(3)}</span>
                      </div>
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full transition-all ${
                            authorityScore >= 0.8 ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' :
                            authorityScore >= 0.5 ? 'bg-gradient-to-r from-blue-500 to-cyan-500' :
                            'bg-gradient-to-r from-slate-500 to-slate-400'
                          }`}
                          style={{ width: `${Math.min(100, authorityScore * 100)}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* QUICK ACTIONS - What You Can Do */}
            <div className="pt-4 border-t border-slate-800">
              <h3 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase mb-3">
                <span>⚡</span> Quick Actions
              </h3>
              <div className="grid grid-cols-2 gap-2">
                <button
                  className="p-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg text-xs font-medium transition-colors border border-emerald-500/30"
                  onClick={() => {
                    // Snapshot-only dashboard: no DB writes here.
                    window.alert('Reinforce is not available in snapshot mode yet.');
                  }}
                >
                  ↑ Reinforce Memory
                </button>
                <button
                  className="p-2 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 rounded-lg text-xs font-medium transition-colors border border-amber-500/30"
                  onClick={() => {
                    setFocusedNode(selectedNode);
                    const topic = selectedNode.topic || selectedNode.full_data?.parsed_props?.topic || '';
                    if (topic && onSearchTermChange) {
                      onSearchTermChange(topic);
                    }
                  }}
                >
                  🔗 Find Related
                </button>
                <button
                  className={`p-2 rounded-lg text-xs font-medium transition-colors border ${
                    storyFocusOn && storyFocusNode?.id === selectedNode.id
                      ? 'bg-cyan-500/20 text-cyan-200 border-cyan-500/40'
                      : 'bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                  }`}
                  onClick={() => {
                    setStoryFocusOn(true);
                    setStoryFocusNode(selectedNode);
                    setFocusedNode(selectedNode);
                  }}
                >
                  🎬 Story Focus
                </button>
                <button
                  className="p-2 bg-slate-500/10 hover:bg-slate-500/20 text-slate-300 rounded-lg text-xs font-medium transition-colors border border-slate-500/30"
                  onClick={() => {
                    setStoryFocusOn(false);
                    setStoryFocusNode(null);
                  }}
                >
                  🧹 Clear Focus
                </button>
                <button
                  className="p-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 rounded-lg text-xs font-medium transition-colors border border-purple-500/30"
                  onClick={() => {
                    window.alert('Edit is not available in snapshot mode yet.');
                  }}
                >
                  ✏️ Edit Memory
                </button>
              </div>
            </div>

            {/* TOP RELATED - Navigation */}
            {(() => {
              const edges = edgesRef.current || [];
              const nodes = nodesRef.current || [];
              const nodeById = new Map(nodes.map((n: any) => [n.id, n] as const));
              const id = selectedNode.id;

              const incident = edges.filter((e: any) => e.source === id || e.target === id);
              const neighbors = incident
                .map((e: any) => {
                  const otherId = e.source === id ? e.target : e.source;
                  const other = nodeById.get(otherId);
                  if (!other || other.type !== 'memory') return null;

                  const t = String(e.type || 'graph');
                  const lbl = String(e.label || 'RELATED');
                  const sim = typeof e.similarity === 'number' ? e.similarity : undefined;

                  const reason =
                    t === 'supersession' ? 'supersession' :
                    t === 'cohesion' && lbl === 'CO_TOPIC' ? 'same topic' :
                    t === 'cohesion' && lbl === 'CO_KNOWLEDGE_TYPE' ? 'same knowledge_type' :
                    t === 'cohesion' && lbl === 'CO_RING' ? 'same ring' :
                    t === 'cohesion' ? 'shared signals' :
                    t === 'graph' ? 'explicit relationship' :
                    t === 'semantic' ? 'semantic similarity' :
                    t;

                  const w =
                    t === 'supersession' ? 100 :
                    t === 'cohesion' && lbl === 'CO_TOPIC' ? 95 :
                    t === 'cohesion' && lbl === 'CO_KNOWLEDGE_TYPE' ? 85 :
                    t === 'cohesion' && lbl === 'CO_RING' ? 75 :
                    t === 'cohesion' ? 70 :
                    t === 'graph' ? 60 :
                    t === 'semantic' ? 50 + (sim ?? 0) :
                    40;

                  return { otherId, other, type: t, label: lbl, similarity: sim, reason, w };
                })
                .filter(Boolean) as Array<any>;

              const seen = new Set<string>();
              const top = neighbors
                .sort((a, b) => b.w - a.w)
                .filter(n => (seen.has(n.otherId) ? false : (seen.add(n.otherId), true)))
                .slice(0, 8);

              if (top.length === 0) return null;

              return (
                <div className="pt-4 border-t border-slate-800">
                  <h3 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase mb-3">
                    <span>🧭</span> Top Related
                  </h3>
                  <div className="space-y-2">
                    {top.map((n, i) => (
                      <button
                        key={`${n.otherId}-${i}`}
                        className="w-full text-left bg-slate-800/30 hover:bg-slate-800/50 border border-slate-800 rounded-lg px-3 py-2 transition-colors"
                        onClick={() => {
                          const target = nodeById.get(n.otherId);
                          if (target) setSelectedNode(target);
                        }}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm text-slate-200 truncate">
                              {String(n.other?.label || n.other?.short_label || n.other?.originalLabel || n.other?.id)}
                            </div>
                            <div className="mt-1 flex flex-wrap gap-2">
                              <span className="px-2 py-0.5 bg-slate-900/60 border border-slate-700 text-[10px] text-slate-300 rounded-full">
                                {n.reason}
                              </span>
                              <span className="px-2 py-0.5 bg-slate-900/60 border border-slate-700 text-[10px] text-slate-500 rounded-full">
                                {n.type}{n.label ? ` • ${n.label}` : ''}{typeof n.similarity === 'number' ? ` • ${n.similarity.toFixed(2)}` : ''}
                              </span>
                            </div>
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">{Math.round(n.w)}</div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })()}

            {/* DEBUG INFO - Collapsed */}
            <details className="pt-4 border-t border-slate-800">
              <summary className="text-[10px] text-slate-600 cursor-pointer hover:text-slate-400">Debug Info</summary>
              <div className="mt-2 p-2 bg-slate-950 rounded text-[10px] font-mono text-slate-600 break-all">
                ID: {selectedNode.id}
              </div>
            </details>
          </div>
        </div>
        );
      })()}
      
      <canvas
        ref={canvasRef}
        className="absolute top-0 left-0 w-full h-full cursor-crosshair z-0"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
      />
    </div>
  );
};

export default GraphCanvas;
