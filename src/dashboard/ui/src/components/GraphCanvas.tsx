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
  type: 'memory' | 'entity' | 'session';
  x: number;
  y: number;
  vx: number;
  vy: number;
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
}

interface Edge {
  source: string;
  target: string;
  type?: string;
  similarity?: number;
}

interface GraphData {
  nodes: any[];
  edges: any[];
}

interface GraphCanvasProps {
  space: string;
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

const GraphCanvas: React.FC<GraphCanvasProps> = ({ space }) => {
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
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [visibleTypes, setVisibleTypes] = useState({
    memory: true,
    entity: false, // PURE THOUGHT MODE: Hide entities by default, show only memory mesh
    session: false
  });
  const draggingNode = useRef<Node | null>(null);
  const offset = useRef({ x: 0, y: 0 }); // Pan offset
  const scale = useRef(1); // Zoom scale
  const isDraggingCanvas = useRef(false);
  
  // Stats for visual debug overlay
  const [nodeCount, setNodeCount] = useState(0);
  const [orphanCount, setOrphanCount] = useState(0);
  const [linkCount, setLinkCount] = useState(0);
  const lastMousePos = useRef({ x: 0, y: 0 });

  // Fetch Data
  useEffect(() => {
    const fetchData = async () => {
      try {
        // CACHE BUSTING: Force fresh network request
        const res = await fetch(`/api/graph?limit=500&space=${space === 'all' ? '' : space}&t=${Date.now()}`);
        const json = await res.json();
        
        console.log("🔍 RAW API RESPONSE:", { nodeCount: json.nodes.length, edgeCount: json.edges.length });
        
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
          const importance = props.importance || 5;
          const layer = props.layer || 'world';
          const sublayer = props.sublayer || 'fact';
          
          // SIZE: Enforce Gravity Hierarchy (SUN → PLANET → SATELLITE)
          let radius;
          if (importance >= 10) {
            radius = 20; // SUN (Critical Laws/Persona)
          } else if (importance >= 8) {
            radius = 12; // PLANET (Preferences/Insights)
          } else {
            radius = 6;  // SATELLITE (Facts/Logs)
          }
          
          // V3 COLOR SCHEME: Layer-aware Gradients
          // SELF: Red-Orange-Yellow
          // WORLD: Blue-Purple-Green
          // INTENT: White-Green-Blue
          let color = '#3b82f6'; // Default Blue

          if (n.type === 'memory') {
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
          } else {
            color = n.type === 'entity' ? '#E6E6FA' : '#FFD700';
          }
          
          // OPACITY: Handle "Redundant" status
          const opacity = props.status === 'redundant' ? 0.5 : 1.0;
          
          // SPRINT 20: CONSISTENT LABELS - Single source of truth
          // 1. Get best available raw title
          let rawTitle = props.cognitive_analysis?.title || props.title || n.label || "Memory";
          
          // 2. SPLIT AT COLON (Critical Step)
          // "IMPORTANCE SCALE CALIBRATION: Correct usage..." -> "IMPORTANCE SCALE CALIBRATION"
          let cleanLabel = rawTitle.split(':')[0].trim();
          
          // 3. Remove noisy prefixes
          cleanLabel = cleanLabel.replace(/^(User|The)\s+(is a|has|preference|is|values)\s?/i, '');
          cleanLabel = cleanLabel.replace(/^User\s/i, '');
          
          // 4. Apply TITLE CASE
          cleanLabel = toTitleCase(cleanLabel);
          
          // 5. Create two versions
          const shortLabel = cleanLabel; // Full clean title for sidebar
          const canvasLabel = cleanLabel.length > 20
            ? cleanLabel.substring(0, 19) + "…"
            : cleanLabel;
          
          return {
            ...n,
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
            sublayer: sublayer // V3
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
        
        // 5. SPRINT 7: GHOST EDGE SCRUBBER - Strict memory-only whitelist
        const memoryNodeIds = new Set(
          processedNodes.filter((n: any) => n.type === 'memory').map((n: any) => n.id)
        );
        
        const safeLinks = cleanEdges.filter((link: any) => {
          // Handle both String IDs and D3 Object References
          const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
          const targetId = typeof link.target === 'object' ? link.target.id : link.target;
          
          // VELVET ROPE: If EITHER end is not a visible memory, KILL THE EDGE
          return memoryNodeIds.has(sourceId) && memoryNodeIds.has(targetId);
        });
        
        // SPRINT 24: ORBITAL TELEPORT - Hard-code orphan positions
        const connectedIds = new Set<string>();
        safeLinks.forEach((link: any) => {
          connectedIds.add(typeof link.source === 'object' ? link.source.id : link.source);
          connectedIds.add(typeof link.target === 'object' ? link.target.id : link.target);
        });
        
        // Separate orphans and cluster
        const orphans = processedNodes.filter((n: any) => !connectedIds.has(n.id));
        const cluster = processedNodes.filter((n: any) => connectedIds.has(n.id));
        
        console.log(`🔧 DNA Mapping complete. Nodes: ${processedNodes.length}, Safe links: ${safeLinks.length}, Orphans: ${orphans.length}, Cluster: ${cluster.length}`);
        
        // SPRINT 25: ORBITAL ANCHOR - Lock orphans with fx/fy
        const canvas = canvasRef.current;
        if (canvas && orphans.length > 0) {
          const width = canvas.width;
          const height = canvas.height;
          const radius = 300; // Reduced to 300px for safer viewport fit
          const centerX = width / 2;
          const centerY = height / 2;
          const angleStep = (2 * Math.PI) / orphans.length;
          
          orphans.forEach((node: any, i: number) => {
            const angle = i * angleStep;
            
            // CALCULATE POSITION
            const targetX = centerX + Math.cos(angle) * radius;
            const targetY = centerY + Math.sin(angle) * radius;
            
            // TELEPORT (Current Position)
            node.x = targetX;
            node.y = targetY;
            
            // *** THE FIX: ANCHOR (Physics Lock) ***
            // Setting fx/fy overrides all simulation forces
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
          
          const newNodes = processedNodes;
          
          // Update stats for visual debug overlay
          setNodeCount(newNodes.length);
          setOrphanCount(orphans.length);
          setLinkCount(safeLinks.length);
          
          nodesRef.current = newNodes;
          edgesRef.current = safeLinks;
          setData({nodes: newNodes, edges: safeLinks});
      } catch (err) {
        console.error("Failed to fetch graph", err);
      }
    };
    
    fetchData();
  }, [space]);

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
      
      // SPRINT 7: CEMENT PHYSICS - Gentle repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          
          // Gentle repulsion (reduced from 500 to 300)
          if (dist < 600) {
            const force = 300 / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            
            nodes[i].vx += fx;
            nodes[i].vy += fy;
            nodes[j].vx -= fx;
            nodes[j].vy -= fy;
          }
          
          // Bounding Box Collision Detection (label-aware)
          const boundsA = getLabelBounds(nodes[i]);
          const boundsB = getLabelBounds(nodes[j]);
          
          // AABB collision check
          if (boundsA.x < boundsB.x + boundsB.width &&
              boundsA.x + boundsA.width > boundsB.x &&
              boundsA.y < boundsB.y + boundsB.height &&
              boundsA.y + boundsA.height > boundsB.y) {
            
            // Apply strong separation force
            const separationForce = 200 / (dist || 1);
            const fx = (dx / dist) * separationForce;
            const fy = (dy / dist) * separationForce;
            
            nodes[i].vx += fx;
            nodes[i].vy += fy;
            nodes[j].vx -= fx;
            nodes[j].vy -= fy;
          }
        }
      }
      
      // SPRINT 7: CEMENT PHYSICS - Loose springs
      edges.forEach(edge => {
        const source = nodes.find(n => n.id === edge.source);
        const target = nodes.find(n => n.id === edge.target);
        
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
      edges.forEach((edge: any) => {
        const sourceId = typeof edge.source === 'object' ? edge.source.id : edge.source;
        const targetId = typeof edge.target === 'object' ? edge.target.id : edge.target;
        connectedIds.add(sourceId);
        connectedIds.add(targetId);
      });
      
      nodes.forEach(node => {
        const isOrphan = !connectedIds.has(node.id);
        
        if (isOrphan) {
          // ORPHAN PHYSICS: Radial gravity to form a ring
          const dx = node.x - cx;
          const dy = node.y - cy;
          const dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const targetRadius = 350; // Ring radius
          
          // Pull towards target radius
          const radiusError = dist - targetRadius;
          const pullStrength = 0.05; // Gentle pull
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
        
        // CEMENT FRICTION: velocityDecay 0.9 (kills movement instantly)
        node.vx *= 0.1; // 1 - 0.9 = 0.1 (90% friction)
        node.vy *= 0.1;
        
        // V3 LAYER GRAVITY: Pull memories to their Anchor
        if (node.type === 'memory' && node.layer) {
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
      });

      // 2. Render Step
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.translate(offset.current.x, offset.current.y);
      ctx.scale(scale.current, scale.current);
      
      // Draw Edges (with semantic edge styling and focus mode)
      const adjacentNodes = new Set<string>();
      if (focusedNode) {
        edges.forEach(edge => {
          if (edge.source === focusedNode.id) adjacentNodes.add(edge.target);
          if (edge.target === focusedNode.id) adjacentNodes.add(edge.source);
        });
      }
      
      edges.forEach(edge => {
        const source = nodes.find(n => n.id === edge.source);
        const target = nodes.find(n => n.id === edge.target);
        if (!source || !target) return;
        
        const isConnected = focusedNode && (edge.source === focusedNode.id || edge.target === focusedNode.id);
        const isSemantic = edge.type === 'semantic';
        const isHovered = hoveredEdge?.source === edge.source && hoveredEdge?.target === edge.target;
        
        // HIGH CONTRAST: Style based on edge type
        if (isSemantic) {
          // AMBER/ORANGE for semantic similarity (high visibility)
          ctx.strokeStyle = isHovered ? 'rgba(245, 158, 11, 1.0)' :  // Amber-500
                           isConnected ? 'rgba(245, 158, 11, 0.8)' : 'rgba(245, 158, 11, 0.6)';
          ctx.setLineDash([4, 4]); // Tighter dash
          ctx.lineWidth = 1.5; // Thicker for visibility
        } else {
          // Solid grey for structural edges (reduced opacity to de-emphasize)
          ctx.strokeStyle = isConnected ? 'rgba(16, 185, 129, 0.6)' : 'rgba(148, 163, 184, 0.15)';
          ctx.setLineDash([]);
          ctx.lineWidth = isConnected ? 2 : 0.5;
        }
        
        ctx.beginPath();
        ctx.moveTo(source.x, source.y);
        ctx.lineTo(target.x, target.y);
        ctx.stroke();
        ctx.setLineDash([]); // Reset dash
        
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
          return allNodes.filter(n => n.type === 'entity' && (n.degree || 0) > 5);
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
        const props = node.full_data?.props || {};
        return node.short_label?.toLowerCase().includes(term) ||
               node.label?.toLowerCase().includes(term) ||
               (props.content || '').toLowerCase().includes(term) ||
               (node.properties?.description || '').toLowerCase().includes(term);
      };
      
      // Filter nodes by visibility toggles
      const visibleNodes = nodes.filter(n => visibleTypes[n.type as keyof typeof visibleTypes]);
      
      // Update pulse phase ONCE per frame
      pulsePhase += PULSE_SPEED;

      // Draw Nodes with shape mapping
      visibleNodes.forEach(node => {
        // Focus mode dimming
        const isFocused = focusedNode?.id === node.id;
        const isAdjacent = focusedNode && adjacentNodes.has(node.id);
        const isDimmed = focusedNode && !isFocused && !isAdjacent;
        const isSearchMatch = matchesSearch(node);
        
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
          ctx.fillStyle = baseColor;
          ctx.shadowColor = baseColor;
          ctx.shadowBlur = 5;
          ctx.globalAlpha = 0.25 * opacity; // Combine dimming with DNA opacity
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
          ctx.shadowBlur = isFocused ? 25 : (10 + heat * 10); // Warmer = more glow
          ctx.globalAlpha = opacity * (0.7 + heat * 0.3); // Warmer = more visible
        }
        
        // Draw shape based on node type
        ctx.save();
        ctx.translate(node.x, node.y);
        
        if (node.type === 'entity') {
          // Diamond shape for entities
          ctx.beginPath();
          ctx.moveTo(0, -node.radius);
          ctx.lineTo(node.radius, 0);
          ctx.lineTo(0, node.radius);
          ctx.lineTo(-node.radius, 0);
          ctx.closePath();
          ctx.fill();
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
        
        ctx.restore();
        ctx.shadowBlur = 0; // Reset shadow
        
        // Draw labels only for visible nodes (semantic zoom)
        if (visibleLabelIds.has(node.id) || isFocused || isSearchMatch) {
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
        
        // Hover effect - show full description
        if (hoveredNode?.id === node.id) {
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Draw detailed tooltip
            const desc = node.properties?.description || node.label;
            const maxWidth = 300;
            const words = desc.split(' ');
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
            
            // Draw tooltip background
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
            
            // Draw tooltip text
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
  const handleMouseDown = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = (e.clientX - rect.left - offset.current.x) / scale.current;
    const y = (e.clientY - rect.top - offset.current.y) / scale.current;
    
    // Check node hit
    const hitNode = nodesRef.current.find(n => {
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
    const hitNode = nodesRef.current.find(n => {
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
      {/* Search Bar */}
      <div className="absolute top-4 left-4 z-10 pointer-events-none">
        <input
          type="text"
          placeholder="Search nodes... (Ctrl+F)"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="px-4 py-2 bg-slate-800 text-white border border-slate-600 rounded-lg focus:outline-none focus:border-emerald-500 w-64 pointer-events-auto"
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setSearchTerm('');
              setFocusedNode(null);
            }
          }}
        />
        {searchTerm && (
          <button
            onClick={() => setSearchTerm('')}
            className="absolute right-2 top-2 text-slate-400 hover:text-white"
          >
            ✕
          </button>
        )}
      
      {/* Visual Debug Overlay - Stats Box */}
      <div className="absolute top-4 right-4 bg-slate-900/90 p-2 rounded border border-slate-700 text-xs font-mono z-50 pointer-events-none">
        <div className="text-green-400">NODES: {nodeCount}</div>
        <div className="text-orange-400">ORPHANS: {orphanCount}</div>
        <div className="text-blue-400">LINKS: {linkCount}</div>
      </div>
      </div>
      
      {/* Node Type Toggles */}
      <div className="absolute top-16 left-4 z-10 bg-slate-800 p-3 rounded-lg border border-slate-600 pointer-events-none">
        <div className="text-sm font-bold mb-2 text-white">Node Types</div>
        {(Object.keys(visibleTypes) as Array<keyof typeof visibleTypes>).map((type) => (
          <label key={type} className="flex items-center gap-2 cursor-pointer text-slate-300 pointer-events-auto">
            <input
              type="checkbox"
              checked={visibleTypes[type]}
              onChange={() => setVisibleTypes(prev => ({...prev, [type]: !prev[type]}))}
              className="pointer-events-auto"
            />
            <span className="capitalize">{type}</span>
          </label>
        ))}
      </div>
      
      {/* Instructions */}
      <div className="absolute top-4 right-4 z-10 bg-slate-800 text-slate-300 px-4 py-2 rounded-lg text-sm border border-slate-600 pointer-events-none">
        <div><strong>Click</strong>: Inspect node</div>
        <div><strong>Shift+Click</strong>: Focus mode</div>
        <div><strong>Drag</strong>: Move nodes</div>
        <div><strong>Scroll</strong>: Zoom</div>
        <div><strong>Esc</strong>: Clear focus/search</div>
      </div>
      
      {/* V28: COGNITIVE MIRROR SIDEBAR - Enhanced Inspector */}
      {selectedNode && (
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
                selectedNode.full_data?.parsed_props?.memory_type === 'decision' ? 'bg-red-500/20 text-red-400' :
                selectedNode.full_data?.parsed_props?.memory_type === 'insight' ? 'bg-purple-500/20 text-purple-400' :
                selectedNode.full_data?.parsed_props?.memory_type === 'preference' ? 'bg-yellow-500/20 text-yellow-400' :
                selectedNode.full_data?.parsed_props?.memory_type === 'episodic' ? 'bg-emerald-500/20 text-emerald-400' :
                'bg-blue-500/20 text-blue-400'
              }`}>
                {selectedNode.full_data?.parsed_props?.memory_type === 'decision' ? '⚖️' :
                 selectedNode.full_data?.parsed_props?.memory_type === 'insight' ? '💡' :
                 selectedNode.full_data?.parsed_props?.memory_type === 'preference' ? '⭐' :
                 selectedNode.full_data?.parsed_props?.memory_type === 'episodic' ? '📝' :
                 '📚'}
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-bold text-white leading-tight">
                  {getCleanTitle(selectedNode)}
                </h2>
                <p className="text-xs text-slate-400 mt-1 uppercase tracking-wider">
                  {selectedNode.full_data?.parsed_props?.memory_type || 'FACT'} • {selectedNode.full_data?.parsed_props?.category || 'General'}
                </p>
              </div>
            </div>
            
            {/* Importance & Heat Indicators */}
            <div className="flex items-center gap-3 mt-4">
              {/* Importance Bar */}
              <div className="flex-1">
                <div className="flex justify-between text-[10px] text-slate-500 mb-1">
                  <span>IMPORTANCE</span>
                  <span className="font-mono">{selectedNode.full_data?.parsed_props?.importance || 5}/10</span>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div 
                    className={`h-full rounded-full transition-all ${
                      (selectedNode.full_data?.parsed_props?.importance || 5) >= 9 ? 'bg-gradient-to-r from-red-500 to-orange-500 animate-pulse' :
                      (selectedNode.full_data?.parsed_props?.importance || 5) >= 7 ? 'bg-gradient-to-r from-yellow-500 to-amber-500' :
                      'bg-gradient-to-r from-cyan-500 to-blue-500'
                    }`}
                    style={{ width: `${(selectedNode.full_data?.parsed_props?.importance || 5) * 10}%` }}
                  />
                </div>
              </div>
              
              {/* Status Badge */}
              <span className={`px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                selectedNode.full_data?.parsed_props?.status === 'verified' ? 'bg-emerald-500/20 text-emerald-400' :
                selectedNode.full_data?.parsed_props?.status === 'contradictory' ? 'bg-red-500/20 text-red-400' :
                'bg-slate-700/50 text-slate-300'
              }`}>
                {selectedNode.full_data?.parsed_props?.status || 'Active'}
              </span>
            </div>
          </div>

          <div className="p-6 space-y-6">
            {/* ACTIONABLE INSIGHT - What This Memory Means */}
            {selectedNode.full_data?.parsed_props?.cognitive_analysis?.strategic_insight && (
              <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 p-4 rounded-xl border border-purple-500/30">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-purple-400">🎯</span>
                  <h4 className="text-xs text-purple-400 uppercase font-bold tracking-wider">Actionable Insight</h4>
                </div>
                <p className="text-sm text-slate-200 leading-relaxed">
                  "{selectedNode.full_data.parsed_props.cognitive_analysis.strategic_insight}"
                </p>
              </div>
            )}

            {/* MEMORY CONTENT - The Core */}
            <div>
              <h3 className="flex items-center gap-2 text-xs font-bold text-cyan-400 uppercase mb-3">
                <span>📄</span> Memory Content
              </h3>
              <div className="bg-slate-800/50 p-4 rounded-xl border-l-4 border-cyan-500 text-slate-300 text-sm leading-relaxed">
                {selectedNode.full_data?.parsed_props?.content || selectedNode.full_data?.description || 'No content available'}
              </div>
            </div>

            {/* METADATA GRID - Quick Facts */}
            <div>
              <h3 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase mb-3">
                <span>📊</span> Metadata
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Created</div>
                  <div className="text-sm text-slate-300 font-mono">
                    {selectedNode.full_data?.created_at ? new Date(selectedNode.full_data.created_at).toLocaleDateString() : 'N/A'}
                  </div>
                </div>
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Domain</div>
                  <div className="text-sm text-slate-300 capitalize">
                    {selectedNode.full_data?.parsed_props?.domain || 'General'}
                  </div>
                </div>
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Intent</div>
                  <div className="text-sm text-slate-300 capitalize">
                    {selectedNode.full_data?.parsed_props?.cognitive_analysis?.intent || selectedNode.full_data?.parsed_props?.intent || 'Reference'}
                  </div>
                </div>
                <div className="bg-slate-800/30 p-3 rounded-lg">
                  <div className="text-[10px] text-slate-500 uppercase">Access Count</div>
                  <div className="text-sm text-slate-300 font-mono">
                    {selectedNode.full_data?.parsed_props?.access_count || 0}×
                  </div>
                </div>
              </div>
            </div>

            {/* TAGS */}
            {selectedNode.full_data?.parsed_props?.tags && (
              <div>
                <h3 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase mb-3">
                  <span>🏷️</span> Tags
                </h3>
                <div className="flex flex-wrap gap-2">
                  {(typeof selectedNode.full_data.parsed_props.tags === 'string' 
                    ? selectedNode.full_data.parsed_props.tags.split(',') 
                    : selectedNode.full_data.parsed_props.tags
                  ).map((tag: string, i: number) => (
                    <span key={i} className="px-2 py-1 bg-slate-800 text-cyan-400 text-xs rounded-full border border-cyan-500/30">
                      {tag.trim()}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* QUICK ACTIONS - What You Can Do */}
            <div className="pt-4 border-t border-slate-800">
              <h3 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase mb-3">
                <span>⚡</span> Quick Actions
              </h3>
              <div className="grid grid-cols-2 gap-2">
                <button className="p-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-lg text-xs font-medium transition-colors border border-emerald-500/30">
                  ↑ Reinforce Memory
                </button>
                <button className="p-2 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 rounded-lg text-xs font-medium transition-colors border border-amber-500/30">
                  🔗 Find Related
                </button>
                <button className="p-2 bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 rounded-lg text-xs font-medium transition-colors border border-purple-500/30">
                  ✏️ Edit Memory
                </button>
                <button className="p-2 bg-slate-500/10 hover:bg-slate-500/20 text-slate-400 rounded-lg text-xs font-medium transition-colors border border-slate-500/30">
                  📦 Archive
                </button>
              </div>
            </div>

            {/* DEBUG INFO - Collapsed */}
            <details className="pt-4 border-t border-slate-800">
              <summary className="text-[10px] text-slate-600 cursor-pointer hover:text-slate-400">Debug Info</summary>
              <div className="mt-2 p-2 bg-slate-950 rounded text-[10px] font-mono text-slate-600 break-all">
                ID: {selectedNode.id}
              </div>
            </details>
          </div>
        </div>
      )}
      
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
