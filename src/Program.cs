using System;
using System.IO;
using SharedCode;
using Deswik.Entities.Cad;
using Deswik.Entities;
using Deswik.Duf;
using Deswik.Serialization;
using System.Collections.Generic;
using System.Reflection;
using System.Linq;
using Deswik.Core.Structures;
using Deswik.Entities.Base;

namespace ConsoleAppNet46
{
    class Program
    {
        static Program()
        {
            AppDomain.CurrentDomain.AssemblyResolve += MyResolveEventHandler;
        }

        private static Assembly MyResolveEventHandler(object sender, ResolveEventArgs args)
        {
            string requestedAssemblyNameSimple = new AssemblyName(args.Name).Name;
            string deswik_install_path = @"C:\DeswikSoftware\DeswikSuite2025.1\Binaries\Release64";

            if (!Directory.Exists(deswik_install_path))
            {
                deswik_install_path = @"C:\Program Files\Deswik\Deswik.Suite 2024.1";
            }

            string fullPathToAssembly = Path.Combine(deswik_install_path, requestedAssemblyNameSimple + ".dll");
            if (File.Exists(fullPathToAssembly))
            {
                Assembly assembly = Assembly.LoadFrom(fullPathToAssembly);
                return assembly;
            }
            return null;
        }

        private static Layer GetLayer(DufDocument doc, string layer_str)
        {
            List<ItemHeader> layer_headers = doc.Duf.GetEntityHeadersWithName(Category.Layers, layer_str);
            ItemHeader layer_header = layer_headers[0];
            Guid layer_guid = layer_header.EntityGuid;

            BaseEntity base_entity = doc.GetEntityByGuid(layer_guid);
            Layer layer = base_entity as Layer;

            return layer;
        }

        static void GetBounds(DufList<Vector4_dp> vertices, out Vector3_dp minBounds, out Vector3_dp maxBounds)
        {
            double minX = double.MaxValue;
            double minY = double.MaxValue;
            double minZ = double.MaxValue;
            double maxX = double.MinValue;
            double maxY = double.MinValue;
            double maxZ = double.MinValue;

            foreach (var vertex in vertices)
            {
                var x = vertex.X;
                var y = vertex.Y;
                var z = vertex.Z;

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

        static dwPolyline CreatePolyline(double[] vertices, bool closeIfNecessary = false)
        {
            var polyline = new dwPolyline();

            if (vertices.Length % 3 != 0)
            {
                // TODO throw better exception?
                throw new Exception("Vertices length not a multiple of 3");
            }

            var verticesCount = vertices.Length;
            int capacity = verticesCount / 3;


            if (closeIfNecessary)
            {
                verticesCount -= 3;

                if (vertices[verticesCount++] != vertices[0] || vertices[verticesCount++] != vertices[1] || vertices[verticesCount++] != vertices[2])
                {
                    capacity += 3;
                }
                else
                {
                    closeIfNecessary = false;
                }
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

            if (closeIfNecessary)
            {
                vertexList.Add(new Vector4_dp(vertices[0], vertices[1], vertices[2], 0));
            }

            polyline.VertexList = vertexList;

            return polyline;
        }

        static void AddPolyline(DufDocument doc, dwPolyline polyline)
        {
            GetBounds(polyline.VertexList, out var minBounds, out var maxBounds);

            doc.AddEntity(polyline, minBounds, maxBounds, polyline.Layer?.Guid);
        }

        static void Main(string[] args)
        {
            string new_key = "new_key";
            string new_value = "new_value";

            // Setup the .duf file
            var path = @"C:\Dev\evo-data-converters\packages\duf\tests\data\brachiopod_with_attrs.duf";
            var path2 = @"C:\Dev\evo-data-converters\packages\duf\tests\data\brachiopod_with_attrs-copy.duf";
            File.Copy(path, path2, true);

            using (var docBefore = new DufDocument(path2))
            {
                docBefore.LoadReferenceEntities();
                docBefore.LoadModelEntities();

                Layer zeroLayer = GetLayer(docBefore, "0");

                // Add layers
                var subLayer = docBefore.AddLayer("NEW_SUB_LAYER", zeroLayer.Guid);
                var topLayer = docBefore.AddLayer("NEW_TOP_LAYER");

                // Add some polylines
                var poly1 = CreatePolyline(new double[] { 0, 0, 0, 5, 0, 0, 5, 5, 0, 0, 5, 0 });
                var poly2 = CreatePolyline(new double[] { 0, 0, 0, -7, 0, 0, -7, -7, 0, 0, -7, 0 }, true);

                poly1.Layer = subLayer;
                poly2.Layer = topLayer;

                AddPolyline(docBefore, poly1);
                AddPolyline(docBefore, poly2);

                DufAttributes.Attribute stringAttr = new DufAttributes.Attribute() { Name = "String Attribute" };
                DufAttributes.Attribute dateTimeAttr = new DufAttributes.Attribute() { Name = "DateTime Attribute", Type = DufAttributes.Attribute.AttributeType.DateTime };
                DufAttributes.Attribute doubleAttr = new DufAttributes.Attribute() { Name = "Double Attribute", Type = DufAttributes.Attribute.AttributeType.Double };
                DufAttributes.Attribute intAttr = new DufAttributes.Attribute() { Name = "Integer Attribute", Type = DufAttributes.Attribute.AttributeType.Integer };

                DufAttributes subLayerAttrs = new DufAttributes(subLayer);
                DufAttributes topLayerAttrs = new DufAttributes(topLayer);

                subLayerAttrs.Add(stringAttr, dateTimeAttr, doubleAttr, intAttr);
                topLayerAttrs.Add(stringAttr, dateTimeAttr, doubleAttr, intAttr);

                stringAttr.SetOnEntity(poly1, "Testing...");
                dateTimeAttr.SetOnEntity(poly1, DateTime.Now);
                doubleAttr.SetOnEntity(poly1, 123.456);
                intAttr.SetOnEntity(poly1, 654321);

                stringAttr.SetOnEntity(poly2);
                dateTimeAttr.SetOnEntity(poly2);
                doubleAttr.SetOnEntity(poly2);
                intAttr.SetOnEntity(poly2);

                var layer_xprops_before = zeroLayer.XProperties;

                Console.WriteLine($"Key present before: {layer_xprops_before.ContainsKey(new_key)}");

                // Trying to edit XProperties
                var props_list = new List<PropValue>();
                props_list.Add(new PropValue(new_value));
                var xprop = new XProperty() { Name = new_key, /* NOTE: XProperty must be named! */ Value = props_list };
                layer_xprops_before.Add(new_key, xprop);
                var new_key_exists = zeroLayer.XProperties.ContainsKey(new_key);
                var new_keys_value = new_key_exists ? zeroLayer.XProperties[new_key].Value.First().Value : "";

                // Confirmed it's set in memory
                Console.WriteLine($"Key present after: {new_key_exists}, value is '{new_keys_value}'");

                // Trying to save changes
                docBefore.Save();
            }

            // Reload the file.
            using (var docAfter = new DufDocument(path2))
            {
                docAfter.LoadReferenceEntities();
                //docAfter.LoadModelEntities(); // Uncomment to load model entities

                Layer layer = GetLayer(docAfter, "0");
                var new_key_exists = layer.XProperties.ContainsKey(new_key);
                var new_keys_value = new_key_exists ? layer.XProperties[new_key].Value.First().Value : "";

                Console.WriteLine($"Key present after reload: {new_key_exists}, value is '{new_keys_value}'");
            }
        }
    }
}
