import React, { useState, useEffect } from "react";
import { Card, Button, Input, Select, Badge, Spinner, Alert } from "@/components/ui";

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  status: string;
  tags: string[];
  author: string;
  created_at: string;
  updated_at: string;
  usage_count: number;
  rating: number;
  review_count: number;
}

interface TemplateMarketplacePageProps {
  onSelectTemplate?: (template: WorkflowTemplate) => void;
}

export function TemplateMarketplacePage({ onSelectTemplate }: TemplateMarketplacePageProps) {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [filteredTemplates, setFilteredTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState("popular");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  const [categories, setCategories] = useState<Array<{ id: string; name: string }>>([]);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    loadTemplates();
    loadCategories();
    loadStats();
  }, []);

  useEffect(() => {
    filterTemplates();
  }, [templates, searchQuery, selectedCategory, sortBy]);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      setError(null);

      let url = "/api/v1/templates";
      if (sortBy === "popular") {
        url = "/api/v1/templates/discover/popular?limit=50";
      } else if (sortBy === "recent") {
        url = "/api/v1/templates/discover/recent?limit=50";
      } else if (sortBy === "rated") {
        url = "/api/v1/templates/discover/top-rated?limit=50";
      }

      const response = await fetch(url);
      if (!response.ok) throw new Error("Failed to load templates");

      const data = await response.json();
      const templateList = data.templates || [];
      setTemplates(templateList);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load templates");
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const response = await fetch("/api/v1/templates/categories/list");
      if (response.ok) {
        const data = await response.json();
        setCategories(data.categories || []);
      }
    } catch (err) {
      console.error("Failed to load categories:", err);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch("/api/v1/templates/stats/overview");
      if (response.ok) {
        const data = await response.json();
        setStats(data.statistics);
      }
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  };

  const filterTemplates = () => {
    let filtered = templates;

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (t) =>
          t.name.toLowerCase().includes(query) ||
          t.description.toLowerCase().includes(query) ||
          t.tags.some((tag) => tag.toLowerCase().includes(query))
      );
    }

    // Filter by category
    if (selectedCategory) {
      filtered = filtered.filter((t) => t.category === selectedCategory);
    }

    setFilteredTemplates(filtered);
  };

  const handleUseTemplate = (template: WorkflowTemplate) => {
    onSelectTemplate?.(template);
  };

  const renderStars = (rating: number) => {
    return (
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((i) => (
          <span key={i} className={i <= Math.round(rating) ? "text-yellow-400" : "text-gray-300"}>
            ★
          </span>
        ))}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border bg-white p-6 shadow-sm">
        <h1 className="text-3xl font-bold mb-2">Template Marketplace</h1>
        <p className="text-gray-600">
          Discover and use pre-built workflow templates to accelerate your automation
        </p>
      </section>

      {/* Statistics */}
      {stats && (
        <section className="grid gap-4 md:grid-cols-4">
          <Card className="p-4">
            <div className="text-sm text-gray-600">Total Templates</div>
            <div className="text-2xl font-bold">{stats.total_templates}</div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-gray-600">Published</div>
            <div className="text-2xl font-bold">{stats.published_templates}</div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-gray-600">Total Usage</div>
            <div className="text-2xl font-bold">{stats.total_usage}</div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-gray-600">Avg Rating</div>
            <div className="text-2xl font-bold">{stats.average_rating.toFixed(1)}</div>
          </Card>
        </section>
      )}

      {/* Search and Filters */}
      <section className="space-y-4">
        <div className="flex gap-4">
          <Input
            placeholder="Search templates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1"
          />
          <Select value={selectedCategory || ""} onChange={(e) => setSelectedCategory(e.target.value || null)}>
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat.id} value={cat.id}>
                {cat.name}
              </option>
            ))}
          </Select>
          <Select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="popular">Most Popular</option>
            <option value="recent">Recently Updated</option>
            <option value="rated">Top Rated</option>
          </Select>
          <Button
            onClick={() => setViewMode(viewMode === "grid" ? "list" : "grid")}
            variant="outline"
          >
            {viewMode === "grid" ? "List" : "Grid"}
          </Button>
        </div>

        {error && <Alert variant="destructive">{error}</Alert>}
      </section>

      {/* Templates */}
      <section>
        {filteredTemplates.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-600">No templates found</p>
          </div>
        ) : viewMode === "grid" ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredTemplates.map((template) => (
              <Card key={template.id} className="p-4 hover:shadow-lg transition-shadow">
                <div className="space-y-3">
                  <div>
                    <h3 className="font-semibold text-lg">{template.name}</h3>
                    <p className="text-sm text-gray-600 line-clamp-2">{template.description}</p>
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    <Badge variant="secondary">{template.category}</Badge>
                    <Badge variant="outline">v{template.version}</Badge>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      {renderStars(template.rating)}
                      <span className="text-gray-600">({template.review_count})</span>
                    </div>
                    <span className="text-gray-600">{template.usage_count} uses</span>
                  </div>

                  <div className="flex gap-2 flex-wrap">
                    {template.tags.slice(0, 3).map((tag) => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>

                  <div className="flex gap-2 pt-2">
                    <Button
                      onClick={() => handleUseTemplate(template)}
                      className="flex-1"
                      size="sm"
                    >
                      Use Template
                    </Button>
                    <Button variant="outline" size="sm">
                      Preview
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredTemplates.map((template) => (
              <Card key={template.id} className="p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold">{template.name}</h3>
                    <p className="text-sm text-gray-600">{template.description}</p>
                    <div className="flex gap-2 mt-2">
                      <Badge variant="secondary" className="text-xs">
                        {template.category}
                      </Badge>
                      <span className="text-xs text-gray-600">{template.usage_count} uses</span>
                      <div className="flex items-center gap-1">
                        {renderStars(template.rating)}
                        <span className="text-xs text-gray-600">({template.review_count})</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      onClick={() => handleUseTemplate(template)}
                      size="sm"
                    >
                      Use
                    </Button>
                    <Button variant="outline" size="sm">
                      Preview
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default TemplateMarketplacePage;
