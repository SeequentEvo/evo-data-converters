using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

using Deswik.Core.Structures;
using Deswik.Duf;
using Deswik.Entities;
using Deswik.Entities.Base;
using Deswik.Entities.Cad;
using Deswik.Serialization;

using DufWrapper;

namespace SimpleDuf
{

    public class SimpleEntity
    {
        public Guid Guid { get; private set; }
        protected DufDocument Duf;

        private void SetGuid(Guid guid)
        {
            Guid = guid;
        }


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
                throw new InvalidOperationException("Entity is not a Primary");
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
    }


    public class SimpleLayer : SimpleEntity
    {
        private DufAttributes _attributes;
        public SimpleLayer(DufDocument document, Guid guid) : base(document, guid)
        {
            if (!(Entity is Layer layer))
            {
                throw new ArgumentException("Entity is not a Layer");
            }

            _attributes = new DufAttributes(layer);
        }

        public DufAttributes.Attribute AddAttribute(string name, AttributeType type)
        {
            if (_attributes.HasAttribute(name))
            {
                throw new ArgumentException($"There is already an attribute with name `{name}`");
            }
            var newAttribute = new DufAttributes.Attribute() { Name = name, Type = type };
            _attributes.Add(newAttribute);
            return newAttribute;
        }

        public DufList<DufAttributes.Attribute> GetAttributes()
        {
            var result = new DufList<DufAttributes.Attribute>();
            for (int i = 0;; i++ )
            {
                var attribute = _attributes[i];
                if (attribute == null)
                {
                    return result;
                }
                result.Add(attribute);
            }
        }
    }

    // TODO This class was set up to provide generic access to DufList<Vector3_dp> and DufList<Vector4_dp>. There's got to be a better way...
    // As it is, it will work, but there is a lot of dynamic overhead added which might be significant. It might have been better to just duplicate
    // Code or use macros.
    internal class VecList3D
    {
        private object _vecList;
        internal int Count;

        internal VecList3D(DufList<Vector3_dp> vec3)
        {
            _vecList = vec3;
            Count = vec3.Count;
        }

        internal VecList3D(DufList<Vector4_dp> vec4)
        {
            _vecList = vec4;
            Count = vec4.Count;
        }

        public static implicit operator VecList3D(DufList<Vector3_dp> vec3) => new VecList3D(vec3);
        public static implicit operator VecList3D(DufList<Vector4_dp> vec4) => new VecList3D(vec4);

        internal void GetXYZ(int i, out double x, out double y, out double z)
        {
            var vecList3 = _vecList as DufList<Vector3_dp>;
            if (vecList3 != null)
            {
                x = vecList3[i].X;
                y = vecList3[i].Y;
                z = vecList3[i].Z;
                return;
            }
            var vecList4 = _vecList as DufList<Vector4_dp>;
            if (vecList4 != null)
            {
                x = vecList4[i].X;
                y = vecList4[i].Y;
                z = vecList4[i].Z;
                return;
            }
            throw new NotSupportedException("The underlying type is neither DufList<Vector3_dp> nor DufList<Vector4_dp>");
        }
    }

    public class SimpleFigure : SimpleEntity
    {
        // TODO I'm avoiding modifying DufDocuments for now. But there's no reason this class should have to keep track of its parent.
        protected Guid _parentLayer;

        public SimpleFigure(DufDocument document, Guid guid, Guid parentLayer) : base(document, guid)
        {
            _parentLayer = parentLayer;
        }

        public void SetAttribute(DufAttributes.Attribute attribute, object value)
        {
            // TODO Guard against bad types. Probably better done in the Attribute class.
            attribute.SetOnEntity(Entity, value);
        }

        internal static void GetBounds(VecList3D vertices, out Vector3_dp minBounds, out Vector3_dp maxBounds)
        {
            double minX = double.MaxValue;
            double minY = double.MaxValue;
            double minZ = double.MaxValue;
            double maxX = double.MinValue;
            double maxY = double.MinValue;
            double maxZ = double.MinValue;

            for (int i = 0; i < vertices.Count; i++)
            {
                vertices.GetXYZ(i, out var x, out var y, out var z);      

                if (x < minX) { minX = x; }
                if (x > maxX) { maxX = x; }
                if (y < minY) { minY = y; }
                if (y > maxY) { maxY = y; }
                if (z < minZ) { minZ = z; }
                if (z > maxZ) { maxZ = z; }
            }

            minBounds = new Vector3_dp(minX, minY, minZ);
            maxBounds = new Vector3_dp(maxX, maxY, maxZ);
        }
    }

    public class SimplePolyline : SimpleFigure
    {
        public SimplePolyline(DufDocument document, Guid guid, Guid parentLayer) : base(document, guid, parentLayer)
        {
            if (!(Entity is dwPolyline polyline))
            {
                throw new ArgumentException("Entity is not a dwPolyline");
            }
        }

        private dwPolyline GetdwPolyline()
        {
            var polyline = Entity as dwPolyline;
            if (polyline == null)
            {
                throw new InvalidOperationException("Entity is not a dwPolyline");
            }
            return polyline;
        }

        public void SetVertices3D(double[] vertices, bool ensureClosed = false)
        {
            var polyline = GetdwPolyline();

            if (vertices.Length % 3 != 0)
            {
                throw new ArgumentException("Vertices must be a multiple of 3");
            }

            var verticesCount = vertices.Length;
            int capacity = verticesCount / 3;

            bool needsClose = ensureClosed && (vertices[verticesCount - 3] != vertices[0] || vertices[verticesCount - 2] != vertices[1] || vertices[verticesCount - 1] != vertices[2]);
            if (needsClose)
            {
                capacity += 1;
            }

            var vertexList = new DufList<Vector4_dp>(capacity);
            int i = 0;

            while (i < verticesCount)
            {
                var x = vertices[i++];
                var y = vertices[i++];
                var z = vertices[i++];

                vertexList.Add(new Vector4_dp(x, y, z, 0));
            }

            if (needsClose)
            {
                vertexList.Add(new Vector4_dp(vertices[0], vertices[1], vertices[2], 0));
            }

            polyline.VertexList = vertexList;

            GetBounds(polyline.VertexList, out var minBounds, out var maxBounds);


            Duf.SetMetadataForEntity(polyline, minBounds, maxBounds, _parentLayer);
        }
    }

    public class SimplePolyface : SimpleFigure
    {
        public SimplePolyface(DufDocument document, Guid guid, Guid parentLayer) : base(document, guid, parentLayer)
        {
            if (!(Entity is dwPolyface polyface))
            {
                throw new ArgumentException("Entity is not a dwPolyface");
            }
        }

        private dwPolyface GetdwPolyface()
        {
            var polyface = Entity as dwPolyface;
            if (polyface == null)
            {
                throw new InvalidOperationException("Entity is not a dwPolyface");
            }
            return polyface;
        }

        public void SetVertices3D(double[] vertices, int[] triangles)
        {
            var polyface = GetdwPolyface();

            if (vertices.Length % 3 != 0)
            {
                throw new ArgumentException("Vertices must be a multiple of 3");
            }

            if (triangles.Length % 3 != 0)
            {
                throw new ArgumentException("Triangles must be a multiple of 3");
            }

            var verticesCount = vertices.Length;
            int vertexCapacity = verticesCount / 3;
            var trianglesCount = triangles.Length;


            var vertexList = new DufList<Vector3_dp>(vertexCapacity);
            var faceList = new DufList<int>(trianglesCount);

            int i = 0;
            while (i < verticesCount)
            {
                var x = vertices[i++];
                var y = vertices[i++];
                var z = vertices[i++];

                vertexList.Add(new Vector3_dp(x, y, z));
            }
            i = 0;
            while (i < trianglesCount)
            {
                faceList.Add(triangles[i++] + 1);  // 1-indexed TODO review
                faceList.Add(triangles[i++] + 1);
                faceList.Add(triangles[i++] + 1);
                faceList.Add(triangles[i - 3] + 1);  // Close the triangle
                faceList.Add(-1);  // TODO What is the 5th value?

            }

            polyface.VertexList = vertexList;
            polyface.FaceList = faceList;

            GetBounds(polyface.VertexList, out var minBounds, out var maxBounds);


            Duf.SetMetadataForEntity(polyface, minBounds, maxBounds, _parentLayer);
        }

    }

    public class Duf
    {
        public DufDocument _duf;

        public Duf(string path)
        {
            if (!File.Exists(path))
            {
                throw new ArgumentException($"File {path} does not exist");
            }

            _duf = new DufDocument(path);
            _duf.LoadReferenceEntities();
            _duf.LoadModelEntities();
        }

        public SimpleLayer GetLayer(string name)
        {
            return new SimpleLayer(_duf, _duf.GetLayer(name).Guid);
        }

        public SimpleEntity NewLayer(string name, Guid? parentLayer = null)
        {
            var newLayer = _duf.AddLayer(name, parentLayer);
            return new SimpleLayer(_duf, newLayer.Guid);
        }

        private void AddFigure(Figure figure, Guid layerGuid)
        {
            var layer = _duf.GetEntityByGuid(layerGuid) as Layer;
            if (layer == null)
            {
                throw new ArgumentException("The Guid is not a layer");
            }
            _duf.AddEntity(figure, parentGuid: layerGuid);
            figure.Layer = layer;
        }

        public SimpleEntity NewPolyline(Guid parentLayer)
        {
            var newPolyline = new dwPolyline();
            AddFigure(newPolyline, parentLayer);
            return new SimplePolyline(_duf, newPolyline.Guid, parentLayer);
        }

        public SimpleEntity NewPolyline(SimpleLayer parentLayer)
        {
            return NewPolyline(parentLayer.Guid);
        }

        public SimpleEntity NewPolyface(Guid parentLayer)
        {
            var newPolyface = new dwPolyface();
            AddFigure(newPolyface, parentLayer);
            return new SimplePolyface(_duf, newPolyface.Guid, parentLayer);
        }

        public SimpleEntity NewPolyface(SimpleLayer parentLayer)
        {
            return NewPolyface(parentLayer.Guid);
        }

        public bool LayerExists(string layerName)
        {
            return _duf.LayerExists(layerName);
        }

        public void Save()
        {
            _duf.Save();
        }

        public void Dispose()
        {
            _duf.Dispose();
        }

    }
}
