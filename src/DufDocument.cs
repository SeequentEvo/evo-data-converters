using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Security.Principal;
using System.Threading.Tasks;

using Deswik.Core.Structures;
using Deswik.Duf;
using Deswik.Entities;
using Deswik.Entities.Cad;
using Deswik.Serialization;

namespace SharedCode
{
    public class DufDocument : IDisposable
    {
        private static readonly Guid _documentPaletteGuid = new Guid("8876D917-BF46-4F20-B6CB-8410B642F784");

        public string FilePath { get; protected set; }

        public DufImplementation<Category> Duf { get; private set; }

        private GuidReferences _guidReferences;

        private Dictionary<Type, Category> _typeToCategoryMap;

        private Dictionary<Category, List<BaseEntity>> _entitiesByCategory;

        private DocumentPalette _documentPalette;

        private Document _document;

        private Dictionary<Guid, EntityMetadata> _addedEntityMetadata;

        private ulong _maxHandleId;

        public DufDocument(string path)
        {
            FilePath = path;

            Duf = new DufImplementation<Category>(FilePath, new Deswik.Entities.Cad.Activator(), new Deswik.Entities.Cad.Upgrader());

            _guidReferences = new GuidReferences();
            _addedEntityMetadata = new Dictionary<Guid, EntityMetadata>();
            _maxHandleId = 0;

            _typeToCategoryMap = new Dictionary<Type, Category>() {
                { typeof(Palette), Category.Palette },
                { typeof(LineType), Category.LineTypes },
                { typeof(Layer), Category.Layers },
                { typeof(Image), Category.Images},
                { typeof(Textstyle), Category.TextStyles },
                { typeof(Block), Category.Blocks },
                { typeof(Dimstyle), Category.DimStyles },
                { typeof(HatchPattern), Category.HatchPatterns },
                { typeof(Light), Category.Lights },
                { typeof(Figure), Category.ModelEntities },
                { typeof(Document), Category.Document },
            };

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
        }

        public void Dispose()
        {
            Duf?.Dispose();
        }

        public BaseEntity GetEntityByGuid(Guid guid)
        {
            return _guidReferences?.GetEntity(guid);
        }

        public void LoadModelEntities(Guid? layerGuid = null)
        {
            var loadedItems = new ConcurrentQueue<BaseEntity>();
            List<Guid?> parents = null;

            if (layerGuid != null)
            {
                parents = new List<Guid?> { layerGuid };
            }

            var loadTask = Task.Run(() => {
                Duf.LoadFromLatestWithConcurrentQueue(loadedItems, _guidReferences, new FilterCriteria<Category> { ParentIds = parents, Categories = new List<Category> { Category.ModelEntities } }, false, true, null);
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

        public void LoadReferenceEntities()
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
            var existingDocGuid = Duf?.Header != null ? Duf.LoadFromLatest(null, new FilterCriteria<Category> { Categories = new List<Category> { Category.Document } }, true, false, null).FirstOrDefault()?.Guid : null;
            Duf.Save(GetSaveSets(existingDocGuid), GetUserName(), saveAsPath, true);
        }

        private void EnsureEntityHasGuidAndHandle(BaseEntity entity)
        {
            if (entity.Guid == Guid.Empty)
            {
                entity.Guid = Guid.NewGuid();
            }

            if (entity.HandleId == 0)
            {
                entity.HandleId = ++_maxHandleId;
            }
        }

        private void SetMetadataForEntity(BaseEntity entity, EntityMetadata metadata)
        {
            EnsureEntityHasGuidAndHandle(entity);

            _addedEntityMetadata[entity.Guid] = metadata;
        }

        public void SetMetadataForEntity(BaseEntity entity, Guid? parentGuid)
        {
            if (parentGuid is null)
            {
                EnsureEntityHasGuidAndHandle(entity);
            }
            else
            {
                SetMetadataForEntity(entity, new EntityMetadata(parentGuid));
            }
        }

        public void SetMetadataForEntity(BaseEntity entity, Vector3_dp? minBounds, Vector3_dp? maxBounds, Guid? parentGuid)
        {
            SetMetadataForEntity(entity, new EntityMetadata(minBounds, maxBounds, parentGuid));
        }

        public void SetMetadataForEntity(BaseEntity entity, Vector3_dp? minBounds, Vector3_dp? maxBounds)
        {
            SetMetadataForEntity(entity, new EntityMetadata(minBounds, maxBounds));
        }

        public void AddEntity(BaseEntity entity)
        {
            var type = entity.GetType();

            EnsureEntityHasGuidAndHandle(entity);

            if (!_typeToCategoryMap.TryGetValue(type, out var category))
            {
                if (entity is Figure figure)
                {
                    category = Category.ModelEntities;

                    if (figure.Layer != null && !_addedEntityMetadata.ContainsKey(entity.Guid))
                    {
                        SetMetadataForEntity(entity, figure.Layer.Guid);
                    }
                }
                else
                {
                    throw new Exception($"Unknown entity type {type.FullName}");
                }
            }

            _entitiesByCategory[category].Add(entity);
            _guidReferences.AddEntity(entity);
        }

        public void AddEntity(BaseEntity entity, Guid? parentGuid)
        {
            SetMetadataForEntity(entity, parentGuid);
            AddEntity(entity);
        }

        public void AddEntity(BaseEntity entity, Vector3_dp? minBounds, Vector3_dp? maxBounds, Guid? parentGuid)
        {
            SetMetadataForEntity(entity, minBounds, maxBounds, parentGuid);
            AddEntity(entity);
        }

        public void AddEntity(BaseEntity entity, Vector3_dp? minBounds, Vector3_dp? maxBounds)
        {
            SetMetadataForEntity(entity, minBounds, maxBounds);
            AddEntity(entity);
        }

        public Layer AddLayer(string name, Guid? parentGuid = null)
        {
            Layer parent = null;

            if (parentGuid is Guid)
            {
                parent = _guidReferences.GetEntity(parentGuid.Value) as Layer;
                name = $"{parent.Name}\\{name}";
            }

            var newLayer = new Layer() { Name = name, Frozen = false };

            AddEntity(newLayer);

            return newLayer;
        }

        private void AddLoadedEntity(Category category, BaseEntity entity)
        {
            if (!_entitiesByCategory.TryGetValue(category, out var baseEntities))
            {
                baseEntities = new List<BaseEntity>();
                _entitiesByCategory.Add(category, baseEntities);
            }

            baseEntities.Add(entity);
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
                Duf.LoadFromLatestWithConcurrentQueue(loadedItems, _guidReferences, new FilterCriteria<Category> { Categories = new List<Category> { category } }, false, true, null);
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

        private SaveEntityItem GetSaveEntityItem(BaseEntity entity)
        {
            SaveEntityItem item;

            if (_addedEntityMetadata.TryGetValue(entity.Guid, out var entityMetadata))
            {
                item = new SaveEntityItem(entity, entityMetadata);
            }
            else
            {
                item = new SaveEntityItem(entity);
            }

            return item;
        }

        private IEnumerable<SaveSet<Category>> GetSaveSets(Guid? existingDocGuid, bool maintainEntityOrdering = false)
        {
            var _guidReferences = new GuidReferences();

            SetDocumentPalette();

            yield return new SaveByEnumerableSet<Category>(new[] { GetSaveEntityItem(_documentPalette) }, Category.Palette, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.LineTypes].Select(x => GetSaveEntityItem(x)), Category.LineTypes, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Images].Select(x => GetSaveEntityItem(x)), Category.Images, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Layers].Select(x => GetSaveEntityItem(x)), Category.Layers, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.TextStyles].Select(x => GetSaveEntityItem(x)), Category.TextStyles, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            var dufBlocks = new List<BaseEntity>();
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Blocks].Select(x =>
            {
                dufBlocks.Add(x);
                return GetSaveEntityItem(x);
            }), Category.Blocks, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, false);

            // NOTE: we add block refs at end not during serialization
            foreach (var block in dufBlocks)
            {
                _guidReferences.AddEntity(block);
            }

            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.DimStyles].Select(x => GetSaveEntityItem(x)), Category.DimStyles, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.HatchPatterns].Select(x => GetSaveEntityItem(x)), Category.HatchPatterns, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Lights].Select(x => GetSaveEntityItem(x)), Category.Lights, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            var modelEntities = _entitiesByCategory[Category.ModelEntities].OfType<Figure>().ToArray();

            yield return new SaveByIndexSet<Category>((entityData) =>
            {
                if (entityData.Position >= modelEntities.Length)
                {
                    entityData.Finished = true;
                    return;
                }

                var entity = modelEntities[entityData.Position];

                if (maintainEntityOrdering && entity is Figure figure)
                {
                    figure.FigureOrder = (uint)entityData.Position + 1;
                }

                entityData.Entity = entity;
            },
            (entityMetadata) =>
            {
                var figure = modelEntities[entityMetadata.Position];
                var layerGuid = figure.Layer.Guid;
                var header = Duf.GetEntityHeader(figure.Guid);

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

        public static XProperty XPropertyGet(XProperties xprops, string name, bool addIfNonExistent = true)
        {
            XProperty found = null;

            if (xprops is XProperties)
            {
                if (xprops.ContainsKey(name))
                {
                    found = xprops[name];
                }
                else if (addIfNonExistent)
                {
                    found = new XProperty() { Name = name };
                    xprops.Add(found);
                }
            }

            return found;
        }

        public static bool XPropertyExists(XProperties xprops, string name)
        {
            return xprops?.ContainsKey(name) ?? false;
        }

        public static bool XPropertyRemove(XProperties xprops, string name)
        {
            return xprops?.Remove(name) ?? false;
        }

        public static bool XPropertySet(XProperties xprops, string name, object value, bool addIfNonExistent = true)
        {
            var exists = false;

            if (xprops is XProperties)
            {
                var xprop = XPropertyGet(xprops, name, addIfNonExistent);

                exists = !(xprop is null);

                if (exists)
                {
                    var propValue = new PropValue(value);

                    if (xprop.Value.Any())
                    {
                        xprop.Value[0] = propValue;
                    }
                    else
                    {
                        xprop.Value.Add(propValue);
                    }
                }
            }

            return exists;
        }
    }
}
