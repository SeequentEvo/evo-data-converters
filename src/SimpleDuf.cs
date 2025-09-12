using System;
using System.Collections;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Security.Principal;
using System.Threading.Tasks;

using Deswik.Core.Structures;
using Deswik.Duf;
using Deswik.Entities;
using Deswik.Entities.Base;
using Deswik.Entities.Cad;
using Deswik.Serialization;

namespace SimpleDuf
{
    // TODO can these have default values? Gemini indicates only C# 10 (.NET 6) or later
    public struct AttributesSpec
    {
        public string Name;
        public string Type;
        public string DefaultValue;
        public string DisplayProperties;
        public string Group;
        public bool Prompt;
        public string Description;
        public string ValuesList;  // TODO check type
        public bool LimitToLit;
        public string LookupList;
        public string Format;
        public bool Required;
        public bool Locked;
        public string WeightField;
        public Int32 DisplayMode;  // TODO needs to be int32?
    }

    public class NewFigure
    {
        public Figure Entity;
        public Vector3_dp MinBounds;
        public Vector3_dp MaxBounds;
        public Guid Parent;
    }


    public class NewLayer
    {
        public Layer Layer;
        public Guid Parent;
    }


    public class SimpleEntity
    {
        public Guid Guid { get; private set; }
        protected DufDocument Duf;
        

        public SimpleEntity(DufDocument document, Guid guid)
        {
            Guid = guid;
            Duf = document;
        }


        private Primary GetPrimary(Guid guid)
        {
            var result = Duf.GetEntityByGuid(guid);
            var primary = result as Primary;
            if (result == null)
            {
                throw new Exception("Entity is not a Primary");
            }
            return primary;
        }

        public Primary Entity
        {
            get
            {
                return GetPrimary(Guid);
            }
        }

        public Primary Layer
        {
            get
            {
                var parentGuid = Duf.GetParentOfNewEntity(Guid);
                return GetPrimary(parentGuid);
            }
        }

        private void SetAttributeToXproperties<T>(string name, T value)
        {
            var props = Entity.XProperties;
            if (props == null)
            {
                props = new XProperties();
                Entity.XProperties = props;
            }
            var props_list = new List<PropValue>();
            props_list.Add(new PropValue(value));
            var xprop = new XProperty() { Name = name, /* NOTE: XProperty must be named! */ Value = props_list };
            props.Add(name, xprop);
        }

        public void SetAttribute(string name, object value)
        {
            var str = value as string;
            if (str != null)
            {
                SetAttributeToXproperties<string>(name, str);
                return;
            }
            throw new Exception("Unhandled value type");
        }

        //public void SetAttributes(IDictionary attributes)
        //{
        //    foreach (DictionaryEntry kvp in attributes)
        //    {
        //        var key = kvp.Key as string;
        //        if (key == null)
        //        {
        //            throw new Exception("Key needs to be a string");
        //        }
        //        SetAttribute(key, kvp.Value);
        //    }
        //}
    }


    public class SimpleLayer : SimpleEntity
    {
        public SimpleLayer(DufDocument document, Guid guid) : base(document, guid)
        {

        }
    }

    public class SimplePolyline : SimpleEntity
    {
   

        public SimplePolyline(DufDocument document, Guid guid) : base(document, guid)
        {

        }

        private void SetVertices3DImpl(double[] vertices, NewFigure newPolyline)
        {
            if (vertices.Length % 3 != 0)
            {
                // TODO throw better exception?
                throw new Exception("Vertices length not a multiple of 3");
            }

            var polyline_entity = newPolyline.Entity as dwPolyline;
            if (polyline_entity == null)
            {
                // TODO better exception
                throw new Exception("Bad type");
            }

            int capacity = vertices.Length / 3;

            var result = new DufList<Vector4_dp>(capacity);

            double minX = 0;
            double minY = 0;
            double minZ = 0;
            double maxX = 0;
            double maxY = 0;
            double maxZ = 0;

            int i = 0;
            while (i < vertices.Length)
            {
                var x = vertices[i++];
                var y = vertices[i++];
                var z = vertices[i++];
                result.Add(
                    new Vector4_dp(
                        x,
                        y,
                        z,
                        0
                    )
                );

                minX = Math.Min(minX, x);
                maxX = Math.Max(maxX, x);
                minY = Math.Min(minY, y);
                maxY = Math.Max(maxY, y);
                minZ = Math.Min(minZ, z);
                maxZ = Math.Max(maxZ, z);

            }
            polyline_entity.VertexList = result;



            newPolyline.MinBounds = new Vector3_dp(minX, minY, minZ);
            newPolyline.MaxBounds = new Vector3_dp(maxX, maxY, maxZ);
        }

        public void SetVertices(double[] vertices, uint dimensions)
        {
            if (dimensions == 3)
            {
            
                SetVertices3DImpl(vertices, Duf.GetNewEntityByGuid(Guid));
                
            }
            else
            {
                // TODO better exception
                throw new Exception($"Unsupported number of dimensions {dimensions}");
            }
        }
    }

    public class DufDocument : IDisposable
    {
        private static readonly Guid _documentPaletteGuid = new Guid("8876D917-BF46-4F20-B6CB-8410B642F784");

        public string Path { get; protected set; }

        private DufImplementation<Category> _duf { get; set; }

        private GuidReferences _guidReferences;

        private Dictionary<Category, List<BaseEntity>> _entitiesByCategory;
        private List<NewFigure> _newModelEntities;
        private Dictionary<Guid, int> _newModelEntitiesByGuid;
        private List<NewLayer> _newLayers;
        private Dictionary<Guid, int> _newLayersByGuid;
        private Dictionary<Guid, Guid> _newParents;
        

        private DocumentPalette _documentPalette;

        private Document _document;

        private ulong _maxHandleId;

        public DufDocument(string path)
        {
            Path = path;

            _duf = new DufImplementation<Category>(Path, new Deswik.Entities.Cad.Activator(), new Deswik.Entities.Cad.Upgrader());

            _guidReferences = new GuidReferences();
            _newModelEntities = new List<NewFigure>();
            _newModelEntitiesByGuid = new Dictionary<Guid, int>();
            _newLayers = new List<NewLayer>();
            _newLayersByGuid = new Dictionary<Guid, int>();

            _entitiesByCategory = new Dictionary<Category, List<BaseEntity>>();

            _entitiesByCategory[Category.Palette] = new List<BaseEntity>();
            _entitiesByCategory[Category.LineTypes] = new List<BaseEntity>();
            _entitiesByCategory[Category.Layers] = new List<BaseEntity>();
            _entitiesByCategory[Category.Images] = new List<BaseEntity>();
            _entitiesByCategory[Category.TextStyles] = new List<BaseEntity>();
            _entitiesByCategory[Category.Blocks] = new List<BaseEntity>();
            _entitiesByCategory[Category.DimStyles] = new List<BaseEntity>();
            _entitiesByCategory[Category.HatchPatterns] = new List<BaseEntity>();
            _entitiesByCategory[Category.Lights] = new List<BaseEntity>();
            _entitiesByCategory[Category.ModelEntities] = new List<BaseEntity>();
            _entitiesByCategory[Category.Document] = new List<BaseEntity>();

            // TODO extend as needed
            //_newEntitiesByCategory[Category.Layers] = new List<NewFigure>();
            //_newEntitiesByCategory[Category.ModelEntities] = new List<NewFigure>();

            _newParents = new Dictionary<Guid, Guid>();

            _maxHandleId = 0;
        }

        // TODO - Probably best not to give the client the option of having an unloaded document
        public void Load()
        {
            LoadReferenceEntities();
            LoadModelEntities();
        }

        public void Dispose()
        {
            _duf?.Dispose();
        }

        public Layer GetLayerByName(string layer_str)
        {
            List<ItemHeader> layer_headers = _duf.GetEntityHeadersWithName(Category.Layers, layer_str);
            ItemHeader layer_header = layer_headers[0];
            Guid layer_guid = layer_header.EntityGuid;

            BaseEntity base_entity = GetLayerByGuid(layer_guid);
            Layer layer = base_entity as Layer;

            return layer;
        }

        internal BaseEntity GetEntityByGuid(Guid guid)
        {
            var result = _guidReferences?.GetEntity(guid);
            if (result != null)
            {
                return result;
            }
            return GetNewEntityByGuid(guid).Entity;
        }

        internal BaseEntity GetLayerByGuid(Guid guid)
        {
            var result = _guidReferences?.GetEntity(guid);
            if (result != null)
            {
                return result;
            }
            return GetNewLayerByGuid(guid).Layer;
        }

        internal NewFigure GetNewEntityByGuid(Guid guid)
        {
            if (_newModelEntitiesByGuid.ContainsKey(guid))
            {
                int pos = _newModelEntitiesByGuid[guid];
                return _newModelEntities[pos];
            }
            else
            {
                throw new Exception("Missing guid for new entity");
            }
        }
        internal NewLayer GetNewLayerByGuid(Guid guid)
        {
            if (_newLayersByGuid.ContainsKey(guid))
            {
                int pos = _newLayersByGuid[guid];
                return _newLayers[pos];
            }
            else
            {
                throw new Exception("Missing guid for new layer");
            }
        }

        internal Guid GetParentOfNewEntity(Guid guid)
        {
            return _newParents[guid];
        }

        public SimpleEntity NewLayer(string name, Guid? parentLayer)
        {
            var layer1 = GetLayerByName("0");
            //var layer2 = GetLayerByName("LAYER TOP");
            //var layer3 = GetLayerByName("LAYER NESTED");

            // TODO I noticed there is a string dictionary "Layers" class. Maybe it would be useful.

            

            var newLayer = new NewLayer();
            newLayer.Layer = new Layer();

            // TODO I'm not sure exactly what to do to properly initialise a layer
            var blueprintLayer = GetLayerByName("0");
            newLayer.Layer.MatchProperties(blueprintLayer);
            newLayer.Layer.HandleId = ++_maxHandleId;
            

            newLayer.Layer.Name = name;
            
            
            var newGuid = Guid.NewGuid();

            _newLayersByGuid[newGuid] = _newLayers.ToArray().Length;
            _newLayers.Add(newLayer);


            if (parentLayer.HasValue)
            {
                newLayer.Parent = parentLayer.Value;
                _newParents[newGuid] = parentLayer.Value;
            }
           

            newLayer.Layer.Guid = newGuid;

            return new SimpleLayer(this, newGuid);
        }

        public SimpleEntity NewPolyline(Guid parentLayer)
        {
            var newPolyline = new NewFigure();
            newPolyline.Entity = new dwPolyline();
            newPolyline.Parent = parentLayer;
            newPolyline.Entity.Layer = GetLayerByGuid(parentLayer) as Layer;  // This might not be needed, but is currently used in GetSaveSets 
            var newGuid = Guid.NewGuid();

            newPolyline.Entity.HandleId = ++_maxHandleId;

            _newModelEntitiesByGuid[newGuid] = _newModelEntities.ToArray().Length;

            _newModelEntities.Add(newPolyline);
            
            _newParents[newGuid] = parentLayer;

            newPolyline.Entity.Guid = newGuid;

            return new SimplePolyline(this, newGuid);
        }

        private void LoadModelEntities(Guid? layerGuid = null)
        {
            var loadedItems = new ConcurrentQueue<BaseEntity>();
            List<Guid?> parents = null;

            if (layerGuid != null)
            {
                parents = new List<Guid?> { layerGuid };
            }

            var loadTask = Task.Run(() => {
                _duf.LoadFromLatestWithConcurrentQueue(loadedItems, _guidReferences, new FilterCriteria<Category> { ParentIds = parents, Categories = new List<Category> { Category.ModelEntities } }, false, true, null);
            });

            while (TaskNotFinished(loadTask) || !loadedItems.IsEmpty)
            {
                if (!loadedItems.TryDequeue(out var entity))
                {
                    System.Threading.Thread.Sleep(10);
                    continue;
                }

                AddLoadedEntity(Category.ModelEntities, entity);
            }
        }

        private void LoadReferenceEntities()
        {
            LoadTopLevelEntitiesOfType(Category.Palette);
            LoadTopLevelEntitiesOfType(Category.LineTypes);
            LoadTopLevelEntitiesOfType(Category.Layers);
            LoadTopLevelEntitiesOfType(Category.Images);
            LoadTopLevelEntitiesOfType(Category.TextStyles);
            LoadTopLevelEntitiesOfType(Category.Blocks);
            LoadTopLevelEntitiesOfType(Category.DimStyles);
            LoadTopLevelEntitiesOfType(Category.HatchPatterns);
            LoadTopLevelEntitiesOfType(Category.Lights);
            LoadTopLevelEntitiesOfType(Category.Document);

            if (_entitiesByCategory.TryGetValue(Category.Palette, out var paletteEntities))
            {
                _documentPalette = paletteEntities.OfType<DocumentPalette>().First();
            }

            if (_entitiesByCategory.TryGetValue(Category.Document, out var documentEntities))
            {
                _document = documentEntities.OfType<Document>().First();
            }
        }

        public void Save(string saveAsPath = null)
        {
            var existingDocGuid = _duf?.Header != null ? _duf.LoadFromLatest(null, new FilterCriteria<Category> { Categories = new List<Category> { Category.Document } }, true, false, null).FirstOrDefault()?.Guid : null;
            _duf.Save(GetSaveSets(existingDocGuid), GetUserName(), saveAsPath, true);
        }

        private void AddLoadedEntity(Category category, BaseEntity entity)
        {
            if (!_entitiesByCategory.TryGetValue(category, out var baseEntities))
            {
                baseEntities = new List<BaseEntity>();
                _entitiesByCategory.Add(category, baseEntities);
            }

            baseEntities.Add(entity);

            _maxHandleId = Math.Max(_maxHandleId, entity.HandleId);
        }

        /// <summary>
        ///     Returns true if the provided task is still executing
        /// </summary>
        /// <param name="task"></param>
        /// <returns></returns>
        private static bool TaskNotFinished(Task task)
        {
            return task.Status != TaskStatus.Canceled &&
                   task.Status != TaskStatus.Faulted &&
                   task.Status != TaskStatus.RanToCompletion;
        }

        private void LoadTopLevelEntitiesOfType(Category category)
        {
            var loadedItems = new ConcurrentQueue<BaseEntity>();
            var loadTask = Task.Run(() => {
                _duf.LoadFromLatestWithConcurrentQueue(loadedItems, _guidReferences, new FilterCriteria<Category> { Categories = new List<Category> { category } }, false, true, null);
            });

            while (TaskNotFinished(loadTask) || !loadedItems.IsEmpty)
            {
                BaseEntity entity;
                if (!loadedItems.TryDequeue(out entity))
                {
                    System.Threading.Thread.Sleep(10);
                    continue;
                }

                AddLoadedEntity(category, entity);
            }
        }

        private void SetDocumentPalette()
        {
            if (_documentPalette == null)
            {
                _documentPalette = new DocumentPalette
                {
                    Guid = _documentPaletteGuid
                };

                _documentPalette.Palette = new Palette(); // TODO: populate this with sensible values
            }
        }

        private SaveByEnumerableSet<Category> GetNewLayersSaveSet(GuidReferences guidReferences)
        {
            return new SaveByEnumerableSet<Category>(
                _newLayers.Select((layer) =>
                {
                    // TODO - need to properly compute the bounds?
                    var metadata = new EntityMetadata(new Vector3_dp(-2, -2, -2), new Vector3_dp(2, 2, 2), layer.Parent);
                    return new SaveEntityItem(layer.Layer, metadata);
                }),
                Category.Layers, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
        }

        private IEnumerable<SaveSet<Category>> GetSaveSets(Guid? existingDocGuid, bool maintainEntityOrdering = false)
        {
            var _guidReferences = new GuidReferences();

            SetDocumentPalette();

            yield return new SaveByEnumerableSet<Category>(new[] { new SaveEntityItem(_documentPalette) }, Category.Palette, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.LineTypes].Select(x => new SaveEntityItem(x)), Category.LineTypes, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Images].Select(x => new SaveEntityItem(x)), Category.Images, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Layers].Select(x => new SaveEntityItem(x)), Category.Layers, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            yield return GetNewLayersSaveSet(_guidReferences);

            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.TextStyles].Select(x => new SaveEntityItem(x)), Category.TextStyles, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            var dufBlocks = new List<BaseEntity>();
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Blocks].Select(x =>
            {
                dufBlocks.Add(x);
                return new SaveEntityItem(x);
            }), Category.Blocks, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, false);

            // NOTE: we add block refs at end not during serialization
            foreach (var block in dufBlocks)
            {
                _guidReferences.AddEntity(block);
            }

            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.DimStyles].Select(x => new SaveEntityItem(x)), Category.DimStyles, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.HatchPatterns].Select(x => new SaveEntityItem(x)), Category.HatchPatterns, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Lights].Select(x => new SaveEntityItem(x)), Category.Lights, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            var initialModelEntities = _entitiesByCategory[Category.ModelEntities].OfType<Figure>().ToArray();

            int numEntities = initialModelEntities.Length + _newModelEntities.ToArray().Length;


            yield return new SaveByIndexSet<Category>((entityData) =>
            {
                if (entityData.Position >= numEntities)
                {
                    entityData.Finished = true;
                    return;
                }

                var entity = entityData.Position < initialModelEntities.Length ? initialModelEntities[entityData.Position] : _newModelEntities[entityData.Position - initialModelEntities.Length].Entity;

                if (maintainEntityOrdering && entity is Figure figure)
                {
                    figure.FigureOrder = (uint)entityData.Position + 1;
                }

                entityData.Entity = entity;
            },
            (entityMetadata) =>
            {
                //var figure = _newModelEntities[entityMetadata.Position - initialModelEntities.Length];

                Figure figure = entityMetadata.Position < initialModelEntities.Length ? initialModelEntities[entityMetadata.Position] : _newModelEntities[entityMetadata.Position - initialModelEntities.Length].Entity;
                //var figure = initialModelEntities[entityMetadata.Position];

                if (figure.Layer == null)
                {
                    throw new Exception("blah");
                }    
                var layerGuid = figure.Layer.Guid;
                

                if (entityMetadata.Position < initialModelEntities.Length)
                {
                    var header = _duf.GetEntityHeader(figure.Guid);
                    if (header is ItemHeader ih)
                    {
                        if (ih.MinX is double minX && ih.MinY is double minY && ih.MinZ is double minZ && ih.MaxX is double maxX && ih.MaxY is double maxY && ih.MaxZ is double maxZ)
                        {
                            entityMetadata.EntityMetadata = new EntityMetadata(new Vector3_dp(minX, minY, minZ), new Vector3_dp(maxX, maxY, maxZ), layerGuid);
                        }
                    }
                    else
                    {
                        entityMetadata.EntityMetadata = new EntityMetadata(layerGuid);
                    }
                }
                else
                {
                    var newFigure = _newModelEntities[entityMetadata.Position - initialModelEntities.Length];
                    entityMetadata.EntityMetadata = new EntityMetadata(newFigure.MinBounds, newFigure.MaxBounds, newFigure.Parent);
                }

                
            }, Category.ModelEntities, false, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, false);

            if (_document.Guid.Equals(Guid.Empty))
            {
                _document.Guid = existingDocGuid ?? Guid.NewGuid();
            }

            yield return new SaveByEnumerableSet<Category>(new[] { new SaveEntityItem(_document) }, Category.Document, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
        }

        private static string GetUserName()
        {
            string username = null;

            try
            {
                username = WindowsIdentity.GetCurrent().Name;
            }
            catch
            {
                try
                {
                    username = Environment.UserName;
                }
                catch
                {
                    // ignored
                }
            }

            if (string.IsNullOrWhiteSpace(username)) username = "unknown";

            return username;
        }
    }
}
